import React from 'react';
import { ShoppingCart, AlertCircle } from 'lucide-react';

export default function MedicineCard({ medicine, onAddToCart }) {
  if (!medicine) return null;

  const price = medicine.price ? Number(medicine.price).toFixed(2) : '0.00';
  const imageUrl = `https://picsum.photos/seed/med-${medicine.id || 'default'}/300/200`;

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden flex flex-col h-full hover:shadow-md transition-shadow duration-200">
      <div className="relative h-48 bg-gray-100">
        <img
          src={imageUrl}
          alt={medicine.name}
          className="w-full h-full object-cover"
          loading="lazy"
        />
        {medicine.requires_prescription && (
          <div className="absolute top-3 right-3 bg-amber-100 text-amber-800 text-xs font-semibold px-2.5 py-1 rounded-full flex items-center gap-1.5 shadow-sm border border-amber-200">
            <AlertCircle size={14} />
            <span>Rx Required</span>
          </div>
        )}
      </div>
      
      <div className="p-5 flex flex-col flex-grow">
        <div className="flex justify-between items-start mb-2 gap-3">
          <h3 className="text-lg font-semibold text-gray-900 line-clamp-2 leading-tight">
            {medicine.name}
          </h3>
          <span className="text-lg font-bold text-blue-600 whitespace-nowrap">
            ${price}
          </span>
        </div>
        
        <p className="text-sm text-gray-500 mb-5 line-clamp-2 flex-grow">
          {medicine.description || 'High-quality pharmaceutical product. Consult your doctor before use.'}
        </p>
        
        <button
          onClick={() => onAddToCart(medicine)}
          className="w-full mt-auto flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white font-medium py-2.5 px-4 rounded-lg transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        >
          <ShoppingCart size={18} />
          <span>Add to Cart</span>
        </button>
      </div>
    </div>
  );
}