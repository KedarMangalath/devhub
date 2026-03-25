import React, { useState } from 'react';
import Button from './Button';
import axios from 'axios';

const Calculator = () => {
  const [input, setInput] = useState('');
  const [result, setResult] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleButtonClick = (value) => {
    if (value === '=') {
      handleCalculate();
    } else {
      setInput(input + value);
      setError('');
    }
  };

  const handleCalculate = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await axios.post('/api/calculate', { expression: input });
      setResult(response.data.result);
    } catch (error) {
      setError('Invalid expression');
      setResult('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className='calculator'>
      <div className='display'>{loading ? <span className='spinner'>Loading...</span> : (result || input)}</div>
      {error && <div className='error'>{error}</div>}
      <div className='buttons'>
        {['1', '2', '3', '+', '4', '5', '6', '-', '7', '8', '9', '*', '0', '=', '/'].map((value) => (
          <Button key={value} value={value} onClick={handleButtonClick} />
        ))}
      </div>
    </div>
  );
};

export default Calculator;