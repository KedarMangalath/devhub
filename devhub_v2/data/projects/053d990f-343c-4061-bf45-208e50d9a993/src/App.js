import React from 'react';
import { BrowserRouter as Router, Route, Switch } from 'react-router-dom';
import Calculator from './components/Calculator';

function App() {
  return (
    <Router>
      <Switch>
        <Route path='/' component={Calculator} />
      </Switch>
    </Router>
  );
}

export default App;