import { Link } from 'react-router-dom'
import { Star, Calendar, Clock } from 'lucide-react'
import Card from '../ui/Card'
import Badge from '../ui/Badge'
import Button from '../ui/Button'

export default function DoctorCard({ doctor }) {
  if (!doctor) return null;

  const availableDate = new Date(doctor.next_available);
  const formattedDate = availableDate.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });
  const formattedTime = availableDate.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  });

  return (
    <Card className="flex flex-col h-full overflow-hidden hover:shadow-md transition-all duration-300 border-slate-200 group">
      <div className="relative h-56 w-full overflow-hidden bg-slate-100">
        <img
          src={doctor.avatar || `https://picsum.photos/seed/${doctor.id}/300/200`}
          alt={doctor.name}
          className="object-cover w-full h-full group-hover:scale-105 transition-transform duration-500"
        />
        <div className="absolute top-3 right-3">
          <Badge variant="secondary" className="bg-white/90 backdrop-blur-sm text-primary font-medium shadow-sm">
            {doctor.specialty_name}
          </Badge>
        </div>
      </div>

      <div className="p-5 flex flex-col flex-grow">
        <div className="mb-1">
          <h3 className="text-lg font-display font-semibold text-slate-900 line-clamp-1">
            {doctor.name}
          </h3>
        </div>

        <div className="flex items-center text-sm text-slate-600 mb-4">
          <div className="flex items-center text-amber-500 bg-amber-50 px-1.5 py-0.5 rounded-md mr-2">
            <Star className="w-3.5 h-3.5 fill-amber-500 mr-1" />
            <span className="font-medium">{doctor.rating}</span>
          </div>
          <span className="text-slate-500">({doctor.reviews_count} reviews)</span>
        </div>

        <div className="bg-slate-50 rounded-xl p-3.5 mb-5 mt-auto border border-slate-100">
          <p className="text-xs text-slate-500 font-medium mb-2.5 uppercase tracking-wider">
            Next Available
          </p>
          <div className="space-y-2">
            <div className="flex items-center text-sm text-slate-700">
              <Calendar className="w-4 h-4 text-primary mr-2.5" />
              <span className="font-medium">{formattedDate}</span>
            </div>
            <div className="flex items-center text-sm text-slate-700">
              <Clock className="w-4 h-4 text-primary mr-2.5" />
              <span>{formattedTime}</span>
            </div>
          </div>
        </div>

        <Link to={`/doctors/${doctor.id}`} className="w-full mt-auto block">
          <Button variant="primary" className="w-full justify-center">
            View Profile
          </Button>
        </Link>
      </div>
    </Card>
  );
}