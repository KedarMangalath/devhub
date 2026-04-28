import { useState } from 'react'
import { Save } from 'lucide-react'

export default function EPrescriptionForm({ onSubmit }) {
  const [medications, setMedications] = useState([
    { name: '', dosage: '', frequency: '', duration: '' }
  ])
  const [instructions, setInstructions] = useState('')

  const handleAddMedication = () => {
    setMedications([...medications, { name: '', dosage: '', frequency: '', duration: '' }])
  }

  const handleRemoveMedication = (index) => {
    const updated = medications.filter((_, i) => i !== index)
    setMedications(updated)
  }

  const handleChange = (index, field, value) => {
    const updated = [...medications]
    updated[index][field] = value
    setMedications(updated)
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const validMedications = medications.filter(m => m.name.trim() !== '')
    onSubmit(validMedications, instructions)
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 flex flex-col h-full">
      <h2 className="text-lg font-semibold text-gray-800 mb-4">E-Prescription</h2>
      
      <form onSubmit={handleSubmit} className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto pr-2 space-y-6">
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-sm font-medium text-gray-700">Medications</h3>
              <button
                type="button"
                onClick={handleAddMedication}
                className="text-sm text-blue-600 hover:text-blue-700 font-medium"
              >
                + Add Medicine
              </button>
            </div>

            {medications.map((med, index) => (
              <div key={index} className="p-4 bg-gray-50 rounded-lg border border-gray-100 relative group">
                {medications.length > 1 && (
                  <button
                    type="button"
                    onClick={() => handleRemoveMedication(index)}
                    className="absolute top-2 right-2 text-gray-400 hover:text-red-500 text-xs font-medium"
                  >
                    Remove
                  </button>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Medicine Name</label>
                    <input
                      type="text"
                      required
                      value={med.name}
                      onChange={(e) => handleChange(index, 'name', e.target.value)}
                      className="w-full text-sm border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 p-2 border bg-white"
                      placeholder="e.g. Amoxicillin"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Dosage</label>
                    <input
                      type="text"
                      required
                      value={med.dosage}
                      onChange={(e) => handleChange(index, 'dosage', e.target.value)}
                      className="w-full text-sm border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 p-2 border bg-white"
                      placeholder="e.g. 500mg"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Frequency</label>
                    <input
                      type="text"
                      required
                      value={med.frequency}
                      onChange={(e) => handleChange(index, 'frequency', e.target.value)}
                      className="w-full text-sm border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 p-2 border bg-white"
                      placeholder="e.g. Twice a day"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Duration</label>
                    <input
                      type="text"
                      required
                      value={med.duration}
                      onChange={(e) => handleChange(index, 'duration', e.target.value)}
                      className="w-full text-sm border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 p-2 border bg-white"
                      placeholder="e.g. 7 days"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Special Instructions
            </label>
            <textarea
              rows={3}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              className="w-full text-sm border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 p-3 border bg-white"
              placeholder="Take after meals, avoid alcohol..."
            />
          </div>
        </div>

        <div className="pt-4 mt-4 border-t border-gray-100">
          <button
            type="submit"
            className="w-full flex justify-center items-center gap-2 bg-blue-600 text-white px-4 py-2.5 rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            <Save className="w-4 h-4" />
            Save Prescription
          </button>
        </div>
      </form>
    </div>
  )
}