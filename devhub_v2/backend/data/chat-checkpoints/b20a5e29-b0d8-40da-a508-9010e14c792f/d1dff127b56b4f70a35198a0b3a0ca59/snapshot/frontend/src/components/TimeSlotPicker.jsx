import React from 'react';
import { Calendar as CalendarIcon } from 'lucide-react';

export default function TimeSlotPicker({ slots = [], selectedSlot, onSelectSlot }) {
  const formatTime = (datetimeStr) => {
    const date = new Date(datetimeStr);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const formatDate = (datetimeStr) => {
    const date = new Date(datetimeStr);
    return date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
  };

  const groupedSlots = slots.reduce((acc, slot) => {
    const dateKey = new Date(slot.datetime).toDateString();
    if (!acc[dateKey]) {
      acc[dateKey] = [];
    }
    acc[dateKey].push(slot);
    return acc;
  }, {});

  if (!slots || slots.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-gray-500 bg-gray-50 rounded-xl border border-dashed border-gray-300">
        <CalendarIcon className="w-10 h-10 mb-3 text-gray-400" />
        <p className="text-sm font-medium">No available slots at the moment</p>
        <p className="text-xs text-gray-400 mt-1">Please check back later or select another date.</p>
      </div>
    );
  }

  return (
    <div className="w-full space-y-6">
      {Object.entries(groupedSlots).map(([dateKey, daySlots]) => (
        <div key={dateKey} className="bg-white p-4 rounded-xl border border-gray-100 shadow-sm">
          <h4 className="text-sm font-semibold text-gray-800 mb-4 flex items-center border-b border-gray-100 pb-2">
            <CalendarIcon className="w-4 h-4 mr-2 text-blue-600" />
            {formatDate(daySlots[0].datetime)}
          </h4>
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-3">
            {daySlots.map((slot, idx) => {
              const isSelected = selectedSlot === slot.datetime;
              return (
                <button
                  key={idx}
                  disabled={!slot.is_available}
                  onClick={() => onSelectSlot(slot.datetime)}
                  className={`
                    py-2 px-1 text-sm font-medium rounded-lg transition-all duration-200 text-center
                    ${
                      !slot.is_available
                        ? 'bg-gray-50 text-gray-400 cursor-not-allowed border border-gray-100'
                        : isSelected
                        ? 'bg-blue-600 text-white shadow-md shadow-blue-200 border border-blue-600 scale-105'
                        : 'bg-white text-gray-700 border border-gray-200 hover:border-blue-400 hover:text-blue-600 hover:shadow-sm'
                    }
                  `}
                >
                  {formatTime(slot.datetime)}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}