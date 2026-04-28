from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db
from models import Order, Medicine
from schemas import OrderCreate, OrderResponse
from auth import get_current_user

router = APIRouter(
    prefix="/api/orders",
    tags=["orders"]
)

@router.post("", response_model=OrderResponse)
def create_order(
    order: OrderCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    total_amount = 0
    
    for item in order.items:
        medicine = db.query(Medicine).filter(Medicine.id == item.medicine_id).first()
        if not medicine:
            raise HTTPException(
                status_code=404, 
                detail=f"Medicine with ID {item.medicine_id} not found"
            )
        
        if medicine.stock < item.quantity:
            raise HTTPException(
                status_code=400, 
                detail=f"Not enough stock for {medicine.name}"
            )
            
        total_amount += (medicine.price * item.quantity)
        medicine.stock -= item.quantity

    new_order = Order(
        patient_id=current_user.id,
        total_amount=total_amount,
        status="Pending",
        shipping_address=order.shipping_address,
        created_at=datetime.utcnow()
    )
    
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    
    return new_order