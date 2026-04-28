import React from 'react';
import Navbar from './Navbar';
import Footer from './Footer';

export default function AppShell({ children }) {
  return (
    <div className="relative flex min-h-screen flex-col bg-background font-body text-text antialiased selection:bg-primary/20 selection:text-primary">
      <Navbar />
      <main className="flex-grow min-h-screen bg-background flex flex-col w-full">
        {children}
      </main>
      <Footer />
    </div>
  );
}