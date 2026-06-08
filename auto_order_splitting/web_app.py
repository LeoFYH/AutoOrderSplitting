from __future__ import annotations

import argparse
import shutil
import uuid
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_file, send_from_directory
from werkzeug.exceptions import HTTPException

from .excel_io import read_orders, read_template, write_debug_workbook, write_purchase_import
from .models import PurchaseLine, SkippedLine, SplitResult, UnmatchedLine
from .normalization import decimal_to_excel
from .splitter import DEFAULT_SKIP_KEYWORDS, split_orders
from .web_state import (
    CURRENT_TEMPLATE,
    RUNS_DIR,
    ensure_data_dirs,
    load_template_items,
    load_template_payload,
    normalize_template_items,
    save_template_items,
    template_item_to_dict,
)


PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "web" / "static"


def create_app() -> Flask:
    ensure_data_dirs()
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 80 * 1024 * 1024

    @app.errorhandler(ValueError)
    def value_error(error: ValueError):
        return jsonify({"error": str(error)}), 400

    @app.errorhandler(HTTPException)
    def http_error(error: HTTPException):
        return jsonify({"error": error.description or error.name}), error.code or 500

    @app.errorhandler(Exception)
    def app_error(error: Exception):
        return jsonify({"error": f"处理失败：{error}"}), 500

    @app.get("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/assets/<path:name>")
    def assets(name: str):
        return send_from_directory(STATIC_DIR, name)

    @app.get("/api/template")
    def get_template():
        payload = load_template_payload()
        if not payload:
            return jsonify({"loaded": False, "sourceName": "", "items": []})
        items = load_template_items()
        return jsonify(
            {
                "loaded": True,
                "sourceName": payload.get("source_name", ""),
                "count": len(items),
                "items": [template_item_to_dict(item) for item in items],
            }
        )

    @app.post("/api/template/upload")
    def upload_template():
        file = request.files.get("template")
        if file is None or not file.filename:
            return jsonify({"error": "请选择模板文件"}), 400
        ensure_data_dirs()
        file.save(CURRENT_TEMPLATE)
        items = read_template(CURRENT_TEMPLATE)
        save_template_items(items, source_name=file.filename)
        return jsonify(
            {
                "sourceName": file.filename,
                "count": len(items),
                "items": [template_item_to_dict(item) for item in items],
            }
        )

    @app.put("/api/template")
    def save_template():
        body = request.get_json(silent=True) or {}
        items = normalize_template_items(body.get("items", []))
        errors = validate_template_items(items)
        if errors:
            return jsonify({"error": "模板存在必填问题", "details": errors[:20]}), 400
        payload = load_template_payload() or {}
        save_template_items(items, source_name=body.get("sourceName") or payload.get("source_name", "手动模板"))
        return jsonify({"count": len(items), "items": [template_item_to_dict(item) for item in items]})

    @app.post("/api/process")
    def process_orders():
        files = request.files.getlist("orders")
        if not files:
            return jsonify({"error": "请选择至少一个订单文件"}), 400

        run_id = uuid.uuid4().hex[:12]
        run_dir = RUNS_DIR / run_id
        orders_dir = run_dir / "orders"
        orders_dir.mkdir(parents=True, exist_ok=True)

        template_file = request.files.get("template")
        if template_file is not None and template_file.filename:
            template_suffix = Path(template_file.filename).suffix or ".xlsx"
            template_path = run_dir / f"采购总模板{template_suffix}"
            template_file.save(template_path)
            template_items = read_template(template_path)
        else:
            template_items = load_template_items()
            if not template_items:
                return jsonify({"error": "请选择采购总模板"}), 400
            if not CURRENT_TEMPLATE.exists():
                return jsonify({"error": "请重新选择采购总模板"}), 400
            template_path = CURRENT_TEMPLATE

        order_paths: list[Path] = []
        for idx, file in enumerate(files, start=1):
            if not file.filename:
                continue
            suffix = Path(file.filename).suffix or ".xlsx"
            target = orders_dir / f"order_{idx}{suffix}"
            file.save(target)
            order_paths.append(target)
        if not order_paths:
            return jsonify({"error": "没有可读取的订单文件"}), 400

        fuzzy_threshold = float(request.form.get("fuzzyThreshold") or 0.88)
        skip_text = request.form.get("skipKeywords") or "营养餐"
        skip_keywords = [item.strip() for item in skip_text.replace("，", ",").split(",") if item.strip()]

        order_lines = read_orders(order_paths)
        result = split_orders(
            template_items,
            order_lines,
            include_template_rows=False,
            skip_keywords=skip_keywords,
            fuzzy_threshold=fuzzy_threshold,
        )

        debug_path = run_dir / "调试明细.xlsx"
        write_debug_workbook(debug_path, result.lines, result.unmatched, result.skipped, result.warnings)

        has_purchase = not result.unmatched
        if has_purchase:
            purchase_path = run_dir / "采购单.xlsx"
            write_purchase_import(template_path, purchase_path, result.lines)

        return jsonify(result_payload(result, run_id, has_purchase=has_purchase))

    @app.get("/download/<run_id>/<path:filename>")
    def download(run_id: str, filename: str):
        path = (RUNS_DIR / run_id / filename).resolve()
        allowed_root = (RUNS_DIR / run_id).resolve()
        if allowed_root not in path.parents and path != allowed_root:
            return jsonify({"error": "下载路径无效"}), 400
        if not path.exists():
            return jsonify({"error": "文件不存在"}), 404
        return send_file(path, as_attachment=True, download_name=path.name)

    @app.post("/api/reset")
    def reset():
        if RUNS_DIR.exists():
            shutil.rmtree(RUNS_DIR)
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        return jsonify({"ok": True})

    return app


def validate_template_items(items) -> list[str]:
    errors: list[str] = []
    for index, item in enumerate(items, start=1):
        if not item.supplier:
            errors.append(f"第{index}行缺少供应商")
        if not item.product:
            errors.append(f"第{index}行缺少商品名称")
        if item.price is None:
            errors.append(f"第{index}行缺少采购单价")
    return errors


def result_payload(result: SplitResult, run_id: str, *, has_purchase: bool) -> dict[str, Any]:
    downloads = {"debug": f"/download/{run_id}/调试明细.xlsx"}
    if has_purchase:
        downloads["purchase"] = f"/download/{run_id}/采购单.xlsx"
    return {
        "runId": run_id,
        "summary": {
            "templateRows": result.template_rows_read,
            "orderRows": result.order_rows_read,
            "purchaseRows": len(result.lines),
            "unmatchedRows": len(result.unmatched),
            "skippedRows": len(result.skipped),
            "warningRows": len(result.warnings),
        },
        "downloads": downloads,
        "lines": [purchase_line_to_dict(line) for line in result.lines[:500]],
        "unmatched": [unmatched_to_dict(line) for line in result.unmatched[:500]],
        "skipped": [skipped_to_dict(line) for line in result.skipped[:500]],
        "warnings": result.warnings[:500],
        "truncated": {
            "lines": len(result.lines) > 500,
            "unmatched": len(result.unmatched) > 500,
            "skipped": len(result.skipped) > 500,
            "warnings": len(result.warnings) > 500,
        },
    }


def purchase_line_to_dict(line: PurchaseLine) -> dict[str, Any]:
    return {
        "owner": line.owner,
        "supplier": line.supplier,
        "product": line.product,
        "unit": line.unit,
        "quantity": decimal_to_excel(line.quantity),
        "price": line.price,
        "productNote": line.product_note,
        "orderNote": line.order_note,
        "note": line.note,
        "agreementPrice": line.agreement_price,
        "matchMethods": sorted(line.match_methods),
    }


def unmatched_to_dict(line: UnmatchedLine) -> dict[str, Any]:
    return {
        "file": line.source_file.name,
        "row": line.row_number,
        "orderNo": line.order_no,
        "customer": line.customer,
        "product": line.product,
        "quantity": decimal_to_excel(line.quantity),
        "unit": line.unit,
        "productNote": line.product_note,
        "orderNote": line.order_note,
        "note": line.note,
        "reason": line.reason,
    }


def skipped_to_dict(line: SkippedLine) -> dict[str, Any]:
    return {
        "file": line.source_file.name,
        "row": line.row_number,
        "orderNo": line.order_no,
        "customer": line.customer,
        "product": line.product,
        "quantity": decimal_to_excel(line.quantity),
        "unit": line.unit,
        "productNote": line.product_note,
        "orderNote": line.order_note,
        "note": line.note,
        "reason": line.reason,
    }


def _bool_form(name: str, *, default: bool) -> bool:
    raw = request.form.get(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="启动本地拆单 Web 工具")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)
    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
