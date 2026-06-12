from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from services.ocr_service import extract_text_from_image, extract_text_from_pdf, validate_image_file
from services.ai_service import extract_expense_data, classify_expense
from services.fraud_service import check_fraud
from models.expense import Expense
from routers.auth_router import get_current_user

router = APIRouter(
    prefix="/expenses",
    tags=["Expenses"]
)


@router.post("/scan-receipt")
async def scan_receipt(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    image_types = [
        "image/jpeg", "image/png", "image/jpg",
        "image/webp", "image/tiff", "image/bmp"
    ]
    pdf_types = ["application/pdf"]
    allowed_types = image_types + pdf_types

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file.content_type} not supported. Supported: JPG, PNG, WEBP, TIFF, BMP, PDF"
        )

    file_bytes = await file.read()

    # Validate file before OCR
    # Rejects blank, empty, or invalid files
    # These are never saved to database
    validation = validate_image_file(file_bytes, file.content_type)
    if not validation["is_valid"]:
        raise HTTPException(
            status_code=400,
            detail=validation["reason"]
        )

    # Run OCR
    if file.content_type in pdf_types:
        ocr_result = extract_text_from_pdf(file_bytes)
    else:
        ocr_result = extract_text_from_image(file_bytes)

    if ocr_result.get("error"):
        raise HTTPException(
            status_code=422,
            detail=f"OCR failed: {ocr_result['error']}"
        )

    if ocr_result["word_count"] < 3:
        raise HTTPException(
            status_code=422,
            detail="Could not extract enough text. Please upload a clearer image or PDF."
        )

    # Run AI extraction
    ai_result = extract_expense_data(ocr_result["cleaned_text"])

    if ai_result["status"] == "error":
        raise HTTPException(
            status_code=500,
            detail=f"AI extraction failed: {ai_result['error']}"
        )

    extracted_data = ai_result["data"]

    # Validate this is actually a receipt
    # If AI cannot find total_amount AND vendor_name,
    # this is not a receipt - reject without saving to DB
    total_amount = extracted_data.get("total_amount")
    vendor_name = extracted_data.get("vendor_name")

    if not total_amount and not vendor_name:
        raise HTTPException(
            status_code=422,
            detail="This file does not appear to be a receipt or bill. No financial data found. Please upload a valid receipt."
        )

    if not total_amount:
        raise HTTPException(
            status_code=422,
            detail="Could not extract total amount from this file. Please upload a clearer receipt."
        )

    # Run AI classification
    classification_result = classify_expense(
        vendor_name=extracted_data.get("vendor_name", "Unknown"),
        line_items=extracted_data.get("line_items", []),
        vendor_hint=extracted_data.get("vendor_category_hint", None)
    )
    classification = classification_result.get("data", {})

    # Run fraud detection
    fraud_result = check_fraud(
        extracted_data=extracted_data,
        classification=classification,
        ocr_confidence=ocr_result["confidence_score"],
        user_id=current_user.id,
        db=db
    )

    # Determine expense status
    # fraud_risk >= 0.5 → pending_verification (needs admin review)
    # fraud_risk < 0.5 → approved (added to expenses immediately)
    if fraud_result["fraud_risk_score"] >= 0.5 or fraud_result["requires_manual_review"]:
        expense_status = "pending_verification"
    else:
        expense_status = "approved"

    # Save to database
    new_expense = Expense(
        user_id=current_user.id,
        status=expense_status,
        vendor_name=extracted_data.get("vendor_name"),
        vendor_category=extracted_data.get("vendor_category_hint"),
        total_amount=extracted_data.get("total_amount"),
        subtotal=extracted_data.get("subtotal"),
        tax_amount=extracted_data.get("tax_amount"),
        tax_type=extracted_data.get("tax_type"),
        currency_code=extracted_data.get("currency_code", "INR"),
        payment_method=extracted_data.get("payment_method"),
        primary_category=classification.get("primary_category"),
        subcategory=classification.get("subcategory"),
        classification_confidence=classification.get("classification_confidence"),
        fraud_risk_score=fraud_result["fraud_risk_score"],
        is_duplicate=fraud_result["is_duplicate"],
        requires_manual_review=fraud_result["requires_manual_review"],
        fraud_flags=fraud_result["fraud_flags"],
        raw_ocr_text=ocr_result["cleaned_text"],
        confidence_score=ocr_result["confidence_score"],
        receipt_number=extracted_data.get("receipt_number"),
        extracted_data=extracted_data,
        transaction_date=extracted_data.get("transaction_date")
    )

    db.add(new_expense)
    db.commit()
    db.refresh(new_expense)

    return {
        "status": "success",
        "expense_id": new_expense.id,
        "expense_status": expense_status,
        "filename": file.filename,
        "file_type": file.content_type,
        "ocr": {
            "confidence_score": ocr_result["confidence_score"],
            "word_count": ocr_result["word_count"],
            "source": ocr_result.get("source", "image"),
            "pages": ocr_result.get("pages", 1)
        },
        "extracted_data": extracted_data,
        "classification": classification,
        "fraud_analysis": fraud_result,
        "message": (
            "Receipt scanned and approved successfully"
            if expense_status == "approved"
            else "Receipt flagged for verification. Please review in the Pending tab."
        )
    }


@router.get("/pending")
def get_pending_expenses(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id,
        Expense.status == "pending_verification"
    ).order_by(Expense.created_at.desc()).all()

    return {
        "status": "success",
        "count": len(expenses),
        "expenses": [
            {
                "id": e.id,
                "vendor_name": e.vendor_name,
                "total_amount": e.total_amount,
                "primary_category": e.primary_category,
                "transaction_date": e.transaction_date,
                "fraud_risk_score": e.fraud_risk_score,
                "fraud_flags": e.fraud_flags,
                "confidence_score": e.confidence_score,
                "status": e.status,
                "created_at": str(e.created_at)
            }
            for e in expenses
        ]
    }


@router.get("/summary")
def get_expense_summary(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # Only approved expenses count in totals
    approved_expenses = db.query(Expense).filter(
        Expense.user_id == current_user.id,
        Expense.status == "approved"
    ).all()

    pending_count = db.query(Expense).filter(
        Expense.user_id == current_user.id,
        Expense.status == "pending_verification"
    ).count()

    rejected_count = db.query(Expense).filter(
        Expense.user_id == current_user.id,
        Expense.status == "rejected"
    ).count()

    if not approved_expenses:
        return {
            "status": "success",
            "total_spend": 0,
            "transaction_count": 0,
            "pending_count": pending_count,
            "rejected_count": rejected_count,
            "avg_transaction": 0,
            "category_breakdown": {},
            "payment_method_breakdown": {}
        }

    total_spend = sum(
        e.total_amount for e in approved_expenses if e.total_amount
    )
    avg_transaction = total_spend / len(approved_expenses)

    category_breakdown = {}
    for e in approved_expenses:
        if e.primary_category and e.total_amount:
            cat = e.primary_category
            category_breakdown[cat] = (
                category_breakdown.get(cat, 0) + e.total_amount
            )

    payment_breakdown = {}
    for e in approved_expenses:
        if e.payment_method:
            method = e.payment_method
            payment_breakdown[method] = payment_breakdown.get(method, 0) + 1

    return {
        "status": "success",
        "total_spend": round(total_spend, 2),
        "transaction_count": len(approved_expenses),
        "pending_count": pending_count,
        "rejected_count": rejected_count,
        "avg_transaction": round(avg_transaction, 2),
        "category_breakdown": category_breakdown,
        "payment_method_breakdown": payment_breakdown
    }


@router.get("/")
def get_all_expenses(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    vendor_name: str = None,
    category: str = None,
    start_date: str = None,
    end_date: str = None,
    min_amount: float = None,
    max_amount: float = None,
    gstin: str = None,
    requires_review: bool = None,
    status: str = None
):
    query = db.query(Expense).filter(
        Expense.user_id == current_user.id
    )

    if status:
        query = query.filter(Expense.status == status)
    else:
        query = query.filter(Expense.status == "approved")

    if vendor_name:
        query = query.filter(
            Expense.vendor_name.ilike(f"%{vendor_name}%")
        )

    if category:
        query = query.filter(
            Expense.primary_category.ilike(f"%{category}%")
        )

    if start_date:
        query = query.filter(Expense.transaction_date >= start_date)

    if end_date:
        query = query.filter(Expense.transaction_date <= end_date)

    if min_amount:
        query = query.filter(Expense.total_amount >= min_amount)

    if max_amount:
        query = query.filter(Expense.total_amount <= max_amount)

    if requires_review is not None:
        query = query.filter(
            Expense.requires_manual_review == requires_review
        )

    query = query.order_by(Expense.created_at.desc())
    expenses = query.all()

    total_spend = sum(e.total_amount for e in expenses if e.total_amount)
    flagged_count = sum(1 for e in expenses if e.requires_manual_review)

    return {
        "status": "success",
        "count": len(expenses),
        "total_spend": round(total_spend, 2),
        "flagged_count": flagged_count,
        "filters_applied": {
            "vendor_name": vendor_name,
            "category": category,
            "start_date": start_date,
            "end_date": end_date,
            "min_amount": min_amount,
            "max_amount": max_amount,
            "gstin": gstin,
            "requires_review": requires_review,
            "status": status or "approved"
        },
        "expenses": [
            {
                "id": e.id,
                "vendor_name": e.vendor_name,
                "total_amount": e.total_amount,
                "primary_category": e.primary_category,
                "subcategory": e.subcategory,
                "transaction_date": e.transaction_date,
                "payment_method": e.payment_method,
                "currency_code": e.currency_code,
                "fraud_risk_score": e.fraud_risk_score,
                "requires_manual_review": e.requires_manual_review,
                "confidence_score": e.confidence_score,
                "receipt_number": e.receipt_number,
                "status": e.status,
                "created_at": str(e.created_at)
            }
            for e in expenses
        ]
    }


@router.put("/{expense_id}/approve")
def approve_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.user_id == current_user.id
    ).first()

    if not expense:
        raise HTTPException(
            status_code=404,
            detail=f"Expense {expense_id} not found"
        )

    if expense.status == "approved":
        raise HTTPException(
            status_code=400,
            detail="Expense is already approved"
        )

    expense.status = "approved"
    db.commit()
    db.refresh(expense)

    return {
        "status": "success",
        "message": f"Expense {expense_id} approved and added to expenses",
        "expense_id": expense_id,
        "new_status": "approved"
    }


@router.put("/{expense_id}/reject")
def reject_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.user_id == current_user.id
    ).first()

    if not expense:
        raise HTTPException(
            status_code=404,
            detail=f"Expense {expense_id} not found"
        )

    if expense.status == "rejected":
        raise HTTPException(
            status_code=400,
            detail="Expense is already rejected"
        )

    expense.status = "rejected"
    db.commit()
    db.refresh(expense)

    return {
        "status": "success",
        "message": f"Expense {expense_id} rejected and archived",
        "expense_id": expense_id,
        "new_status": "rejected"
    }


@router.get("/{expense_id}")
def get_expense_by_id(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.user_id == current_user.id
    ).first()

    if not expense:
        raise HTTPException(
            status_code=404,
            detail=f"Expense with id {expense_id} not found"
        )

    return {
        "status": "success",
        "expense": {
            "id": expense.id,
            "vendor_name": expense.vendor_name,
            "vendor_category": expense.vendor_category,
            "total_amount": expense.total_amount,
            "subtotal": expense.subtotal,
            "tax_amount": expense.tax_amount,
            "tax_type": expense.tax_type,
            "currency_code": expense.currency_code,
            "payment_method": expense.payment_method,
            "primary_category": expense.primary_category,
            "subcategory": expense.subcategory,
            "classification_confidence": expense.classification_confidence,
            "transaction_date": expense.transaction_date,
            "receipt_number": expense.receipt_number,
            "fraud_risk_score": expense.fraud_risk_score,
            "fraud_flags": expense.fraud_flags,
            "requires_manual_review": expense.requires_manual_review,
            "confidence_score": expense.confidence_score,
            "extracted_data": expense.extracted_data,
            "status": expense.status,
            "created_at": str(expense.created_at)
        }
    }


@router.delete("/{expense_id}")
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.user_id == current_user.id
    ).first()

    if not expense:
        raise HTTPException(
            status_code=404,
            detail=f"Expense with id {expense_id} not found"
        )

    db.delete(expense)
    db.commit()

    return {
        "status": "success",
        "message": f"Expense {expense_id} deleted successfully"
    }