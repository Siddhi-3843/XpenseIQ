from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models.expense import Expense


def check_fraud(
    extracted_data: dict,
    classification: dict,
    ocr_confidence: float,
    user_id: int,
    db: Session
) -> dict:

    fraud_flags = []
    fraud_risk_score = 0.0

    total_amount = extracted_data.get("total_amount", 0) or 0
    vendor_name = extracted_data.get("vendor_name", "") or ""
    transaction_date = extracted_data.get("transaction_date", "") or ""
    receipt_number = extracted_data.get("receipt_number", None)

    # RULE 1 — Low OCR confidence
    if ocr_confidence < 0.60:
        fraud_flags.append("Low OCR confidence — receipt may be unclear or fake")
        fraud_risk_score += 0.25

    # RULE 2 — Suspiciously round amount
    if total_amount > 0 and total_amount % 1000 == 0:
        fraud_flags.append(f"Suspiciously round amount: ₹{total_amount}")
        fraud_risk_score += 0.20

    # RULE 3 — Missing receipt number
    if not receipt_number:
        fraud_flags.append("Missing receipt number")
        fraud_risk_score += 0.10

    # ─────────────────────────────────────────
    # RULE 3b — Mathematical inconsistency
    # If line items exist, verify that
    # sum(quantity × unit_price) ≈ total_amount
    # AI-generated bills often get math wrong
    # ─────────────────────────────────────────
    line_items = extracted_data.get("line_items", [])
    if line_items and total_amount:
        try:
            calculated_total = sum(
                (item.get("quantity") or 1) * (item.get("unit_price") or 0)
                for item in line_items
                if item.get("unit_price")
            )
            if calculated_total > 0:
                discrepancy_pct = abs(calculated_total - total_amount) / total_amount * 100
                if discrepancy_pct > 10:
                    fraud_flags.append(
                        f"Mathematical inconsistency: line items sum to "
                        f"Rs {calculated_total:,.2f} but bill total is Rs {total_amount:,.2f} "
                        f"({discrepancy_pct:.1f}% discrepancy) — possible AI-generated bill"
                    )
                    fraud_risk_score += 0.35
        except Exception:
            pass    

    # ─────────────────────────────────────────
    # RULE 3c — GSTIN validation
    # Real GSTINs have a valid format AND checksum
    # AI-generated bills often have fake GSTINs
    # that look real but fail checksum verification
    # ─────────────────────────────────────────
    gstin = extracted_data.get("gstin", None)
    if gstin:
        gstin_result = validate_gstin(gstin)
        if not gstin_result["is_valid_format"]:
            fraud_flags.append(
                f"Invalid GSTIN format: '{gstin}' — "
                f"{gstin_result['reason']} — possible AI-generated bill"
            )
            fraud_risk_score += 0.30
        elif not gstin_result["is_valid_checksum"]:
            fraud_flags.append(
                f"GSTIN checksum failed: '{gstin}' — "
                f"{gstin_result['reason']} — possible AI-generated bill"
            )
            fraud_risk_score += 0.40    

    # RULE 4 — Weekend transaction for B2B vendor
    if transaction_date:
        try:
            txn_date = datetime.strptime(transaction_date, "%Y-%m-%d")
            is_weekend = txn_date.weekday() in [5, 6]
            primary_category = classification.get("primary_category", "")
            business_categories = ["Office & Supplies", "Finance"]
            if is_weekend and primary_category in business_categories:
                fraud_flags.append(
                    f"Weekend transaction for business vendor on {transaction_date}"
                )
                fraud_risk_score += 0.20
        except ValueError:
            fraud_flags.append("Invalid or unreadable transaction date")
            fraud_risk_score += 0.15

    # RULE 5 — Duplicate detection
    duplicate_check = check_duplicate(
        vendor_name=vendor_name,
        total_amount=total_amount,
        transaction_date=transaction_date,
        receipt_number=receipt_number,
        user_id=user_id,
        db=db
    )

    if duplicate_check["is_duplicate"]:
        fraud_flags.append(
            f"DUPLICATE BILL DETECTED — This bill is an exact copy of "
            f"Expense ID #{duplicate_check['duplicate_id']} "
            f"already submitted on {duplicate_check['duplicate_date']}"
        )
        fraud_risk_score += 0.60

    elif duplicate_check["is_near_duplicate"]:
        fraud_flags.append(
            f"POSSIBLE DUPLICATE — A very similar bill from the same vendor "
            f"was submitted recently (Expense ID #{duplicate_check['duplicate_id']}). "
            f"Please verify this is not a duplicate submission."
        )
        fraud_risk_score += 0.35

    # RULE 6 — High value transaction
    if total_amount > 50000:
        fraud_flags.append(f"High value transaction: ₹{total_amount}")
        fraud_risk_score += 0.15

    # ─────────────────────────────────────────
    # RULE 7 — AI-generated bill detection
    # Checks for demo keywords, fake GSTINs,
    # templated invoice numbers, generic vendors
    # ─────────────────────────────────────────
    ai_check = check_ai_generated_indicators(extracted_data)
    if ai_check["ai_flags"]:
        for ai_flag in ai_check["ai_flags"]:
            fraud_flags.append(f"AI-GENERATED BILL DETECTED: {ai_flag}")
        fraud_risk_score += ai_check["ai_score_addition"]

    # Also check raw extracted data string for DEMO UPI patterns
    raw_text = str(extracted_data).upper()
    if "DEMOUPI" in raw_text or "DEMO-UPI" in raw_text or "TESTUPI" in raw_text:
        fraud_flags.append(
            "AI-GENERATED BILL DETECTED: Transaction ID contains 'DEMO' UPI pattern — "
            "real UPI transaction IDs are numeric only"
        )
        fraud_risk_score += 0.45

    # Check GSTIN PAN digits for sequential patterns
    if gstin and len(gstin) == 15:
        pan_digits = gstin[7:11]
        if pan_digits in ["1234", "5678", "0000", "1111", "9999", "1230"]:
            fraud_flags.append(
                f"AI-GENERATED BILL DETECTED: GSTIN '{gstin}' contains sequential "
                f"digits '{pan_digits}' in PAN — common in AI-generated fake GSTINs"
            )
            fraud_risk_score += 0.35

    # Cap the fraud risk score at 1.0
    fraud_risk_score = min(round(fraud_risk_score, 2), 1.0)
    requires_manual_review = fraud_risk_score >= 0.5

    return {
        "fraud_risk_score": fraud_risk_score,
        "fraud_flags": fraud_flags,
        "is_duplicate": duplicate_check["is_duplicate"],
        "is_near_duplicate": duplicate_check["is_near_duplicate"],
        "duplicate_match_id": duplicate_check.get("duplicate_id"),
        "requires_manual_review": requires_manual_review,
        "review_reason": ", ".join(fraud_flags) if fraud_flags else None
    }


def check_duplicate(
    vendor_name: str,
    total_amount: float,
    transaction_date: str,
    receipt_number: str,
    user_id: int,
    db: Session
) -> dict:

    result = {
        "is_duplicate": False,
        "is_near_duplicate": False,
        "duplicate_id": None,
        "duplicate_date": None
    }

    if not vendor_name or not total_amount:
        return result

    try:
        ninety_days_ago = datetime.now() - timedelta(days=90)

        recent_expenses = db.query(Expense).filter(
            Expense.user_id == user_id,
            Expense.created_at >= ninety_days_ago
        ).all()

        for expense in recent_expenses:
            if not expense.vendor_name:
                continue

            vendor_match = (
                expense.vendor_name.lower().strip() == vendor_name.lower().strip()
            )

            if not vendor_match:
                continue

            # Check 1 — Same receipt number = definite duplicate
            if (
                receipt_number and
                expense.receipt_number and
                receipt_number.strip() == expense.receipt_number.strip()
            ):
                result["is_duplicate"] = True
                result["duplicate_id"] = expense.id
                result["duplicate_date"] = str(expense.created_at)[:10]
                return result

            # Check 2 — Same vendor + same amount + same date = exact duplicate
            if (
                expense.total_amount == total_amount and
                expense.transaction_date == transaction_date
            ):
                result["is_duplicate"] = True
                result["duplicate_id"] = expense.id
                result["duplicate_date"] = str(expense.created_at)[:10]
                return result

            # Check 3 — Same vendor + amount within 5% = near duplicate
            if expense.total_amount:
                amount_diff_pct = abs(
                    expense.total_amount - total_amount
                ) / total_amount * 100

                if amount_diff_pct <= 5:
                    result["is_near_duplicate"] = True
                    result["duplicate_id"] = expense.id
                    result["duplicate_date"] = str(expense.created_at)[:10]

    except Exception:
        pass

    return result

def validate_gstin(gstin: str) -> dict:
    """
    Validates GSTIN format and checksum.
    
    GSTIN format: 2-digit state code + 10-char PAN + 1-digit entity + Z + 1 checksum
    Example: 27AABCU9603R1ZX
    """
    import re

    result = {
        "is_valid_format": False,
        "is_valid_checksum": False,
        "state_code": None,
        "reason": None
    }

    if not gstin or len(gstin) != 15:
        result["reason"] = "GSTIN must be exactly 15 characters"
        return result

    gstin = gstin.upper().strip()

    # Format check
    pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
    if not re.match(pattern, gstin):
        result["reason"] = "GSTIN format invalid — does not match standard pattern"
        return result

    result["is_valid_format"] = True

    # State code check (valid Indian state codes: 01-37)
    state_code = int(gstin[:2])
    if state_code < 1 or state_code > 37:
        result["reason"] = f"Invalid state code: {gstin[:2]}"
        return result

    result["state_code"] = gstin[:2]

    # Checksum validation (Luhn-style algorithm used by GST)
    try:
        chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        total = 0
        for i, char in enumerate(gstin[:-1]):
            val = chars.index(char)
            if i % 2 == 1:
                val *= 2
            total += val // len(chars) + val % len(chars)

        checksum_char = chars[(len(chars) - (total % len(chars))) % len(chars)]

        if gstin[-1] == checksum_char:
            result["is_valid_checksum"] = True
        else:
            result["reason"] = (
                f"GSTIN checksum invalid — expected '{checksum_char}' "
                f"but got '{gstin[-1]}' — possible fake or AI-generated GSTIN"
            )
    except Exception as e:
        result["reason"] = f"Checksum calculation failed: {str(e)}"

    return result


def check_ai_generated_indicators(extracted_data: dict) -> dict:
    """
    Checks for indicators that a bill may be AI-generated or fake.
    Looks for patterns humans and billing software don't produce.
    """
    import re
    flags = []
    score = 0.0

    vendor_name   = (extracted_data.get("vendor_name") or "").upper()
    receipt_number= (extracted_data.get("receipt_number") or "").upper()
    gstin         = (extracted_data.get("gstin") or "").upper()
    vendor_category = (extracted_data.get("vendor_category_hint") or "").upper()

    # ── Check 1: Suspicious keywords in vendor/invoice fields ────────
    demo_keywords = [
        "DEMO", "TEST", "SAMPLE", "FAKE", "DUMMY",
        "PLACEHOLDER", "EXAMPLE", "TEMPLATE", "MOCK"
    ]
    for field_name, field_value in [
        ("vendor name", vendor_name),
        ("invoice number", receipt_number),
    ]:
        for kw in demo_keywords:
            if kw in field_value:
                flags.append(
                    f"Suspicious keyword '{kw}' found in {field_name} — "
                    f"likely a demo or AI-generated bill"
                )
                score += 0.55
                break

    # ── Check 2: Sequential/alphabetical PAN in GSTIN ────────────────
    # Real PAN: first 5 letters are derived from taxpayer name
    # AI-generated: often produces ABCDE, AAAAA, ABCAB patterns
    if len(gstin) == 15:
        pan_letters = gstin[2:7]  # positions 2-6 are first 5 letters of PAN

        # Check for purely sequential letters e.g. ABCDE, BCDEF
        is_sequential = all(
            ord(pan_letters[i+1]) - ord(pan_letters[i]) == 1
            for i in range(len(pan_letters) - 1)
        )
        if is_sequential:
            flags.append(
                f"GSTIN '{gstin}' contains sequential letters '{pan_letters}' in PAN — "
                f"real GSTINs derive PAN from taxpayer name, not alphabet sequences"
            )
            score += 0.45

        # Check for all-same letters e.g. AAAAA, BBBBB
        if len(set(pan_letters)) == 1:
            flags.append(
                f"GSTIN '{gstin}' contains repeated letters '{pan_letters}' — "
                f"suspicious, likely AI-generated"
            )
            score += 0.50

        # Check for common fake PAN patterns
        fake_pan_patterns = ["ABCDE", "AAAAA", "XXXXX", "ZZZZZ", "TTTTT", "PPPPP"]
        if pan_letters in fake_pan_patterns:
            flags.append(
                f"GSTIN '{gstin}' uses known fake PAN pattern '{pan_letters}'"
            )
            score += 0.55

    # ── Check 3: Invoice number contains date in filename format ─────
    # AI tools often generate: DEMO-INV-20260624-1045
    # Real invoices: INV-001, TAX/2026/001, etc.
    date_in_invoice = re.search(r'20\d{6}', receipt_number)
    if date_in_invoice and len(receipt_number) > 15:
        flags.append(
            f"Invoice number '{receipt_number}' contains an embedded timestamp — "
            f"AI tools commonly generate invoice numbers this way"
        )
        score += 0.20

    # ── Check 4: Vendor name looks generic/templated ─────────────────
    generic_vendor_patterns = [
        r"^DEMO\s", r"\bONLINE\s+PVT\b", r"^SAMPLE\s",
        r"^TEST\s+(VENDOR|COMPANY|STORE|MART)",
        r"\bDEMO\s+(MART|STORE|SHOP|COMPANY)\b",
    ]
    for pat in generic_vendor_patterns:
        if re.search(pat, vendor_name):
            flags.append(
                f"Vendor name '{vendor_name}' matches a generic/template pattern — "
                f"typical of AI-generated or sample bills"
            )
            score += 0.40
            break

    return {
        "ai_flags": flags,
        "ai_score_addition": min(round(score, 2), 0.80)
    }