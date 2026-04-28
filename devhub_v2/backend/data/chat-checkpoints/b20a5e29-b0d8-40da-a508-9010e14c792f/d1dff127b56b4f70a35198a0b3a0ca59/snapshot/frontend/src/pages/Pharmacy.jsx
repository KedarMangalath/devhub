import { useState, useEffect } from 'react'
import { getMedicines, createOrder } from '../api/endpoints.js'
import Navbar from '../components/Navbar.jsx'
import MedicineCard from '../components/MedicineCard.jsx'
import CartDrawer from '../components/CartDrawer.jsx'
import CheckoutModal from '../components/CheckoutModal.jsx'
import Footer from '../components/Footer.jsx'
import { ShoppingBag } from 'lucide-react'

export default function Pharmacy() {
  const [medicines, setMedicines] = useState([])
  const [cartItems, setCartItems] = useState([])
  const [isCartOpen, setIsCartOpen] = useState(false)
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false)

  useEffect(() => {
    getMedicines().then(setMedicines).catch(console.error)
  }, [])

  const handleAddToCart = (medicine) => setCartItems([...cartItems, medicine])
  const handleRemove = (id) => setCartItems(cartItems.filter(item => item.id !== id))
  const handleCheckout = () => {
    setIsCartOpen(false)
    setIsCheckoutOpen(true)
  }
  const handleSubmitOrder = async (shipping_address) => {
    try {
      await createOrder({ items: cartItems, shipping_address })
      setIsCheckoutOpen(false)
      setCartItems([])
    } catch (err) {
      console.error(err)
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <Navbar />
      <main className="flex-grow max-w-7xl mx-auto px-4 py-8 w-full">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Pharmacy</h1>
          <button 
            onClick={() => setIsCartOpen(true)}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
          >
            <ShoppingBag className="w-5 h-5" />
            <span>Cart ({cartItems.length})</span>
          </button>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {medicines.map(med => (
            <MedicineCard key={med.id} medicine={med} onAddToCart={handleAddToCart} />
          ))}
        </div>
      </main>
      <CartDrawer 
        isOpen={isCartOpen} 
        onClose={() => setIsCartOpen(false)} 
        cartItems={cartItems} 
        onRemove={handleRemove} 
        onCheckout={handleCheckout} 
      />
      <CheckoutModal 
        isOpen={isCheckoutOpen} 
        onClose={() => setIsCheckoutOpen(false)} 
        total={cartItems.reduce((sum, item) => sum + (item.price || 0), 0)} 
        onSubmit={handleSubmitOrder} 
      />
      <Footer />
    </div>
  )
}