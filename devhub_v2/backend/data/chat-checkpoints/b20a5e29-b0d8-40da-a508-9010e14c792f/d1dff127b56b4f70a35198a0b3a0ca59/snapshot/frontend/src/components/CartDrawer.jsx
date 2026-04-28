import React, { useEffect } from 'react';
import { X, Trash2, ShoppingBag } from 'lucide-react';

export default function CartDrawer({ isOpen, onClose, cartItems = [], onRemove, onCheckout }) {
  // Prevent body scroll when drawer is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

  const total = cartItems.reduce((sum, item) => {
    const quantity = item.quantity || 1;
    return sum + (item.price * quantity);
  }, 0);

  return (
    <div 
      className={`fixed inset-0 z-50 transition-opacity duration-300 ${
        isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
      }`}
    >
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black bg-opacity-50 transition-opacity" 
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer Panel */}
      <div 
        className={`absolute inset-y-0 right-0 w-full max-w-md bg-white shadow-2xl transform transition-transform duration-300 ease-in-out flex flex-col ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <ShoppingBag className="w-5 h-5 text-blue-600" />
            Your Cart
          </h2>
          <button 
            onClick={onClose} 
            className="p-2 -mr-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full transition-colors"
            aria-label="Close cart"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Cart Items */}
        <div className="flex-1 overflow-y-auto p-6">
          {cartItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500 space-y-4">
              <div className="w-20 h-20 bg-gray-50 rounded-full flex items-center justify-center mb-2">
                <ShoppingBag className="w-10 h-10 text-gray-300" />
              </div>
              <p className="text-lg font-medium text-gray-900">Your cart is empty</p>
              <p className="text-sm text-center">Looks like you haven't added any medicines to your cart yet.</p>
              <button 
                onClick={onClose}
                className="mt-4 text-blue-600 font-medium hover:text-blue-700"
              >
                Continue Shopping
              </button>
            </div>
          ) : (
            <ul className="space-y-6">
              {cartItems.map((item) => (
                <li key={item.id} className="flex items-start space-x-4">
                  <img 
                    src={item.image_url || `https://picsum.photos/seed/${item.id}/300/200`} 
                    alt={item.name} 
                    className="w-20 h-20 object-cover rounded-lg border border-gray-200 flex-shrink-0" 
                  />
                  <div className="flex-1 min-w-0">
                    <h3 className="text-base font-medium text-gray-900 truncate">{item.name}</h3>
                    <p className="text-sm text-gray-500 mt-1">{item.dosage || 'Standard Dosage'}</p>
                    <div className="flex items-center justify-between mt-2">
                      <p className="text-sm font-semibold text-blue-600">
                        ${Number(item.price).toFixed(2)}
                      </p>
                      <p className="text-sm text-gray-600">
                        Qty: {item.quantity || 1}
                      </p>
                    </div>
                  </div>
                  <button 
                    onClick={() => onRemove(item.id)} 
                    className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-full transition-colors flex-shrink-0"
                    aria-label={`Remove ${item.name} from cart`}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Footer / Checkout */}
        {cartItems.length > 0 && (
          <div className="border-t border-gray-200 bg-gray-50 p-6">
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm text-gray-600">Subtotal</span>
              <span className="text-sm font-medium text-gray-900">${total.toFixed(2)}</span>
            </div>
            <div className="flex justify-between items-center mb-6">
              <span className="text-base font-semibold text-gray-900">Total</span>
              <span className="text-xl font-bold text-blue-600">${total.toFixed(2)}</span>
            </div>
            <button
              onClick={onCheckout}
              className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-blue-700 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 shadow-sm"
            >
              Proceed to Checkout
            </button>
          </div>
        )}
      </div>
    </div>
  );
}