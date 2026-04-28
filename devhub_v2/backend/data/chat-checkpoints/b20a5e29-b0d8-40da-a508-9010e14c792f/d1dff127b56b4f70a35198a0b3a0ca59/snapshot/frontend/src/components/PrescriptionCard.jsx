import { Pill, FileText } from 'lucide-react'

export default function PrescriptionCard({ prescription }) {
  if (!prescription) return null;

  const {
    doctor_name = 'Unknown Doctor',
    created_at = new Date().toISOString(),
    medications = [],
    instructions = 'No additional instructions provided.',
  } = prescription;

  const formattedDate = new Date(created_at).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 hover:shadow-md transition-shadow duration-200">
      <div className="flex justify-between items-start mb-4 pb-4 border-b border-gray-100">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Dr. {doctor_name}</h3>
          <p className="text-sm text-gray-500">Prescribed on {formattedDate}</p>
        </div>
        <div className="bg-blue-50 p-2 rounded-full">
          <FileText className="w-5 h-5 text-blue-600" />
        </div>
      </div>

      <div className="space-y-3 mb-5">
        <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Medications</h4>
        {medications.length > 0 ? (
          <ul className="space-y-2">
            {medications.map((med, index) => (
              <li key={index} className="flex items-start gap-3 bg-gray-50 p-3 rounded-lg border border-gray-100">
                <Pill className="w-4 h-4 text-indigo-500 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-gray-900">{med.name}</p>
                  <p className="text-xs text-gray-600 mt-0.5">
                    {med.dosage && `${med.dosage} • `}
                    {med.frequency && `${med.frequency} • `}
                    {med.duration && `${med.duration}`}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-gray-500 italic">No medications listed.</p>
        )}
      </div>

      <div className="bg-amber-50 rounded-lg p-4 border border-amber-100">
        <h4 className="text-xs font-bold text-amber-800 uppercase tracking-wider mb-1">Instructions & Notes</h4>
        <p className="text-sm text-amber-900 leading-relaxed">{instructions}</p>
      </div>
    </div>
  );
}