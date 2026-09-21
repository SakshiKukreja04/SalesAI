"""Vision Agent module for SalesAI multimodal understanding.

Extracts visual information from email image attachments, maps detected items
to the ShopiFyX product catalog, identifies damage/defects, and cross-checks
against placed customer orders for consistency guardrails.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from app.config import settings
from app.memory.memory_models import VisualContext

LOGGER = logging.getLogger(__name__)

# Maximum token budget / dimensions for vision processing
MAX_IMAGE_DIM = 1024
MAX_PROMPT_CHARS = 1200


def _extract_json_block(text: str) -> str:
    """Extract first valid JSON object from model output."""
    if not text:
        return ""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return ""
    return text[start : end + 1]


def _prepare_image_bytes(raw_b64: str) -> Optional[bytes]:
    """Safely decode base64 image data and downscale if PIL is available."""
    if not raw_b64:
        return None

    try:
        clean_b64 = re.sub(r"\s+", "", str(raw_b64)).replace("-", "+").replace("_", "/")
        padding = "=" * (-len(clean_b64) % 4)
        image_bytes = base64.b64decode(clean_b64 + padding)

        # Optional PIL downscaling to respect token budget
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(image_bytes))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # Downscale if larger than MAX_IMAGE_DIM
            if img.width > MAX_IMAGE_DIM or img.height > MAX_IMAGE_DIM:
                img.thumbnail((MAX_IMAGE_DIM, MAX_IMAGE_DIM), Image.Resampling.LANCZOS)
                out_io = io.BytesIO()
                img.save(out_io, format="JPEG", quality=85)
                return out_io.getvalue()
        except ImportError:
            pass

        return image_bytes
    except Exception as exc:
        LOGGER.warning("Failed to decode or process image bytes: %s", exc)
        return None


def _call_gemini_vision(prompt: str, image_bytes_list: List[bytes], mime_types: List[str]) -> str:
    """Invoke Gemini Vision with multimodal image parts."""
    api_key = getattr(settings, "gemini_api_key", None) or os.getenv("GEMINI_API_KEY", "")
    if not api_key or not image_bytes_list:
        return ""

    model_candidates = [
        "gemini-3.6-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ]

    # Try official google.genai client (v1)
    try:
        from google import genai
        # pyrefly: ignore [missing-import]
        from google.genai import types
        client = genai.Client(api_key=api_key)

        parts = []
        for img_bytes, mime in zip(image_bytes_list, mime_types):
            parts.append(types.Part.from_bytes(data=img_bytes, mime_type=mime or "image/jpeg"))
        parts.append(prompt)

        for model_name in model_candidates:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=parts,
                )
                text = (getattr(response, "text", "") or "").strip()
                if text:
                    return text
            except Exception as e:
                LOGGER.debug("google.genai vision attempt on %s failed: %s", model_name, e)
                continue
    except ImportError:
        pass

    # Try legacy google.generativeai client
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        parts = []
        for img_bytes, mime in zip(image_bytes_list, mime_types):
            parts.append({"mime_type": mime or "image/jpeg", "data": img_bytes})
        parts.append(prompt)

        for model_name in model_candidates:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(parts)
                text = (getattr(response, "text", "") or "").strip()
                if text:
                    return text
            except Exception as e:
                LOGGER.debug("google.generativeai vision attempt on %s failed: %s", model_name, e)
                continue
    except ImportError:
        LOGGER.debug("No Google GenAI package available for vision inference")

    return ""


def _call_groq_fallback(prompt: str) -> str:
    """Invoke Groq text inference as fallback when Gemini vision quota is exhausted."""
    api_key = os.getenv("GROQ_API_KEY", "").strip() or getattr(settings, "groq_api_key", "")
    if not api_key:
        return ""

    try:
        from groq import Groq
        client = Groq(api_key=api_key)

        for model_name in ["openai/gpt-oss-20b", "qwen/qwen3.8-27b", "allam-2-7b"]:
            try:
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=model_name,
                    temperature=0.1,
                    max_tokens=400,
                )
                text = (chat_completion.choices[0].message.content or "").strip()
                if text:
                    return text
            except Exception as exc:
                LOGGER.debug("Groq fallback attempt on %s failed: %s", model_name, exc)
                continue
    except Exception as e:
        LOGGER.debug("Groq client error: %s", e)

    return ""



def _match_product_with_order_history(
    detected_product_name: str,
    detected_category: str,
    matched_sku: str,
    customer_orders: Optional[List[Dict[str, Any]]],
    customer_message: str = "",
) -> tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """Cross-verify detected product and customer message against placed orders in Neo4j graph.
    
    Returns: (matches_order, matched_order_number, resolved_product_name, resolved_sku)
    """
    if not customer_orders:
        det_name = (detected_product_name or "").strip()
        return False, None, det_name if det_name else None, None

    det_name_clean = (detected_product_name or "").lower().strip()
    det_sku_clean = (matched_sku or "").lower().strip()
    msg_clean = (customer_message or "").lower()

    generic_stopwords = {"product", "item", "order", "delivery", "package", "parcel", "box", "shipment", "thing", "unknown", "attached", "none"}

    # 1. First check if visual detected SKU or Name directly matches an ordered product
    for order in customer_orders:
        order_num = order.get("order_number") or order.get("id") or "Unknown"
        products = order.get("products") or []
        for prod in products:
            p_name = prod.get("name") or ""
            p_name_lower = p_name.lower()
            p_sku = (prod.get("sku") or "").lower()

            # Direct SKU match
            if det_sku_clean and det_sku_clean != "none" and det_sku_clean == p_sku:
                return True, str(order_num), p_name, prod.get("sku")

            # Non-generic name match
            if det_name_clean and det_name_clean not in generic_stopwords and (det_name_clean in p_name_lower or p_name_lower in det_name_clean):
                return True, str(order_num), p_name, prod.get("sku")

            # Word overlap (1+ distinctive keywords)
            det_words = {w for w in re.findall(r"\b[a-z0-9]{3,}\b", det_name_clean) if w not in generic_stopwords}
            prod_words = {w for w in re.findall(r"\b[a-z0-9]{3,}\b", p_name_lower) if w not in generic_stopwords}
            if det_words and len(det_words.intersection(prod_words)) >= 1:
                return True, str(order_num), p_name, prod.get("sku")

    # 2. If visual detection was generic or uncertain, check if email message text explicitly references an ordered product
    for order in customer_orders:
        order_num = order.get("order_number") or order.get("id") or "Unknown"
        products = order.get("products") or []
        for prod in products:
            p_name = prod.get("name") or ""
            p_name_lower = p_name.lower()
            prod_words = {w for w in re.findall(r"\b[a-z0-9]{4,}\b", p_name_lower) if w not in generic_stopwords}
            
            # Check if distinctive product words appear in customer message (e.g. 'speaker', 'soundmax', 'backpack', 'cabin')
            for pw in prod_words:
                if re.search(r"\b" + re.escape(pw) + r"\b", msg_clean):
                    return True, str(order_num), p_name, prod.get("sku")

    # 3. If customer message or visual explicitly names an un-ordered product (e.g. 'crop top', 't-shirt', 'sandal')
    for un_kw in ["crop top", "croptop", "jeans", "formal shoe", "air fryer", "kettle", "watch", "earbuds"]:
        if un_kw in msg_clean or un_kw in det_name_clean:
            return False, None, un_kw.title(), None

    det_fallback = det_name_clean.title() if (det_name_clean and det_name_clean not in generic_stopwords) else "Attached item"
    return False, None, det_fallback, None



def analyze_email_images(
    images: List[Dict[str, Any]],
    customer_message: str = "",
    customer_orders: Optional[List[Dict[str, Any]]] = None,
) -> VisualContext:
    """Analyze email image attachments using Gemini Vision grounded in catalog & order context."""
    if not images:
        return VisualContext(has_images=False)

    image_bytes_list: List[bytes] = []
    mime_types: List[str] = []

    for img in images[:3]:  # Max 3 images to bound token budget
        raw_data = img.get("data") or ""
        mime = img.get("mime_type") or "image/jpeg"
        decoded = _prepare_image_bytes(raw_data)
        if decoded:
            image_bytes_list.append(decoded)
            mime_types.append(mime)

    if not image_bytes_list:
        return VisualContext(has_images=True, image_count=len(images), summary="Attached images could not be parsed.")

    # Format customer's placed orders into prompt for direct cross-reference
    orders_context_lines = []
    if customer_orders:
        for ord_info in customer_orders[:5]:
            onum = ord_info.get("order_number") or "Order"
            prods = ", ".join([p.get("name", "") for p in ord_info.get("products", []) if p.get("name")])
            orders_context_lines.append(f"- {onum}: {prods}")
    orders_context_str = "\n".join(orders_context_lines) if orders_context_lines else "No placed orders found."

    prompt = (
        "You are the ShopiFyX E-Commerce Vision Analysis Agent.\n\n"
        "TASK:\n"
        "Analyze the provided image attachment(s) from a customer support email.\n\n"
        "CUSTOMER MESSAGE CONTEXT:\n"
        f"\"{customer_message[:300]}\"\n\n"
        "CUSTOMER'S ACTIVE PLACED ORDERS ON FILE:\n"
        f"{orders_context_str}\n\n"
        "SHOPIFYX PRODUCT TAXONOMY:\n"
        "- Electronics & Audio (Bluetooth Speakers, Earbuds, Headphones, Power Banks, Smartwatches, Smart Plugs)\n"
        "- Accessories & Luggage (Cabin Backpacks, Laptop Backpacks, Hard Shell Cabin Cases, Packing Cubes, Tote Bags, Sling Bags)\n"
        "- Fashion & Footwear (Running Shoes, Sneakers, Formal Shoes, Sandals, Jackets, Hoodies, Shirts, Crop Tops, Jeans)\n"
        "- Home & Kitchen (Air Fryers, Electric Kettles, Blender Grinders, Non-Stick Cookware Sets)\n\n"
        "OUTPUT REQUIREMENT:\n"
        "Return ONLY a JSON object with this exact schema:\n"
        "{\n"
        '  "detected_product_name": "<name of product in image, e.g. SoundMax Bluetooth Speaker, Floral Crop Top, AeroStride Running Shoes, or Unknown>",\n'
        '  "detected_category": "<Apparel | Audio | Luggage | Footwear | Kitchenware | Electronics | Receipt | Other>",\n'
        '  "matched_catalog_sku": "<e.g. ELX-002, AL-003, FW-009, or null if not a recognized ShopiFyX product>",\n'
        '  "is_catalog_product": true | false,\n'
        '  "visual_condition": "intact | damaged | torn | wrong_item | defective | unclear",\n'
        '  "defect_type": "<sole_delamination | torn_seam | cracked_grille | cracked_screen | wrong_item | cosmetic_scratch | stain | broken_part | none>",\n'
        '  "severity_level": "<severe_unusable | moderate_functional | minor_cosmetic | none>",\n'
        '  "defect_area_ratio": <float between 0.0 and 1.0 representing percentage of visible product area affected by defect>,\n'
        '  "diagnostic_reasoning": "<1-2 sentences technical reasoning describing physical defect location, severity, and cause>",\n'
        '  "defect_description": "<concise description of physical defect, tear, broken part, or none>",\n'
        '  "is_receipt_or_invoice": true | false,\n'
        '  "visual_confidence": <float between 0.0 and 1.0>,\n'
        '  "summary": "<1 sentence factual summary of what the image shows>"\n'
        "}"
    )

    raw_response = _call_gemini_vision(prompt, image_bytes_list, mime_types) or _call_groq_fallback(prompt)

    if raw_response:
        json_str = _extract_json_block(raw_response)
        if json_str:
            try:
                data = json.loads(json_str)
                det_product = data.get("detected_product_name") or "Unknown item"
                det_cat = data.get("detected_category") or "Other"
                sku = data.get("matched_catalog_sku")
                is_catalog = bool(data.get("is_catalog_product", False))
                cond = data.get("visual_condition") or "unclear"
                defect_type = data.get("defect_type") or ("damaged_item" if cond in ("damaged", "torn", "defective") else "none")
                severity = data.get("severity_level") or ("moderate_functional" if cond in ("damaged", "torn", "defective") else "none")
                
                try:
                    dar = float(data.get("defect_area_ratio") or (0.30 if cond in ("damaged", "torn", "defective") else 0.0))
                    dar = max(0.0, min(1.0, dar))
                except (ValueError, TypeError):
                    dar = 0.25 if cond in ("damaged", "torn", "defective") else 0.0

                diag_reason = data.get("diagnostic_reasoning") or data.get("defect_description") or ""
                defect = data.get("defect_description") or diag_reason
                is_receipt = bool(data.get("is_receipt_or_invoice", False))
                conf = float(data.get("visual_confidence") or 0.85)
                summary = data.get("summary") or f"Customer provided image of {det_product} ({cond})."

                # Cross verify against customer order history
                matches_order, matched_onum, resolved_pname, resolved_sku = _match_product_with_order_history(
                    detected_product_name=det_product,
                    detected_category=det_cat,
                    matched_sku=sku or "",
                    customer_orders=customer_orders,
                    customer_message=customer_message,
                )

                final_product_name = resolved_pname or det_product
                final_sku = resolved_sku or sku
                if resolved_sku:
                    is_catalog = True

                return VisualContext(
                    has_images=True,
                    image_count=len(image_bytes_list),
                    detected_product_name=final_product_name,
                    detected_category=det_cat,
                    matched_catalog_sku=final_sku,
                    is_catalog_product=is_catalog,
                    visual_condition=cond,
                    defect_type=defect_type,
                    severity_level=severity,
                    defect_area_ratio=dar,
                    diagnostic_reasoning=diag_reason,
                    defect_description=defect,
                    is_receipt_or_invoice=is_receipt,
                    visual_confidence=conf,
                    summary=summary,
                    matches_order_history=matches_order,
                    matched_order_number=matched_onum,
                )
            except Exception as exc:
                LOGGER.warning("Failed to parse vision model JSON response: %s", exc)

    # Fallback heuristic if vision API is unavailable / off
    matches_order, matched_onum, resolved_pname, resolved_sku = _match_product_with_order_history(
        detected_product_name="",
        detected_category="",
        matched_sku="",
        customer_orders=customer_orders,
        customer_message=customer_message,
    )

    return VisualContext(
        has_images=True,
        image_count=len(image_bytes_list),
        detected_product_name=resolved_pname or "Attached product",
        detected_category="General",
        matched_catalog_sku=resolved_sku,
        is_catalog_product=bool(resolved_sku),
        visual_condition="unclear",
        defect_type="none",
        severity_level="none",
        defect_area_ratio=0.0,
        diagnostic_reasoning="",
        defect_description="",
        visual_confidence=0.60 if matches_order else 0.40,
        summary=f"Customer attached {len(image_bytes_list)} image(s) regarding {resolved_pname or 'product'}.",
        matches_order_history=matches_order,
        matched_order_number=matched_onum,
    )
