import { Heart, Brain, Baby, Stethoscope, Activity } from 'lucide-react'
import { Link } from 'react-router-dom'

const getIconForSpecialty = (name) => {
  const lowerName = name.toLowerCase();
  
  if (lowerName.includes('cardio')) {
    return <Heart className="w-8 h-8 text-rose-500" />;
  }
  if (lowerName.includes('neuro')) {
    return <Brain className="w-8 h-8 text-purple-500" />;
  }
  if (lowerName.includes('pediatric') || lowerName.includes('child')) {
    return <Baby className="w-8 h-8 text-sky-500" />;
  }
  if (lowerName.includes('general') || lowerName.includes('internal') || lowerName.includes('family')) {
    return <Stethoscope className="w-8 h-8 text-emerald-500" />;
  }
  
  return <Activity className="w-8 h-8 text-indigo-500" />;
};

export default function SpecialtyGrid({ specialties = [] }) {
  if (!specialties || specialties.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 px-4 text-gray-500 bg-gray-50 rounded-3xl border border-dashed border-gray-200">
        <Activity className="w-12 h-12 text-gray-300 mb-4" />
        <p className="text-lg font-medium text-gray-600">No specialties available</p>
        <p className="text-sm text-gray-400 mt-1">Please check back later for updates.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 md:gap-6">
      {specialties.map((specialty, index) => (
        <Link
          key={specialty.name || index}
          to={`/doctors?specialty=${encodeURIComponent(specialty.name)}`}
          className="flex flex-col items-center justify-center p-6 bg-white rounded-3xl shadow-sm border border-gray-100 hover:shadow-lg hover:-translate-y-1 hover:border-indigo-100 transition-all duration-300 group cursor-pointer"
        >
          <div className="p-4 bg-gray-50 rounded-2xl group-hover:bg-indigo-50 group-hover:scale-110 transition-all duration-300 mb-5">
            {getIconForSpecialty(specialty.name)}
          </div>
          
          <h3 className="text-sm md:text-base font-bold text-gray-800 text-center mb-2 group-hover:text-indigo-600 transition-colors line-clamp-1">
            {specialty.name}
          </h3>
          
          <div className="flex items-center space-x-1">
            <span className="text-xs font-medium text-gray-500 bg-gray-100 px-3 py-1 rounded-full group-hover:bg-indigo-100 group-hover:text-indigo-700 transition-colors">
              {specialty.count} {specialty.count === 1 ? 'Doctor' : 'Doctors'}
            </span>
          </div>
        </Link>
      ))}
    </div>
  );
}