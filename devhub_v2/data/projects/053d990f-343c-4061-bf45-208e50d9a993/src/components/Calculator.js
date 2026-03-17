import React, { useState } from 'react';
import Button from './Button';
import axios from 'axios';

const Calculator = () => {
  const [input, setInput] = useState('');
  const [result, setResult] = useState('');

  const handleButtonClick = (value) => {
    if (value === '=') {
      handleCalculate();
    } else {
      setInput(input + value);
    }
  };

  const handleCalculate = async () => {
    try {
      const response = await axios.post('/api/calculate', { expression: input });
      setResult(response.data.result);
    } catch (error) {
      setResult('Error');
    }
  };

  return (
    <div className='calculator'>
      <div className='display'>{result || input}</div>
      <div className='buttons'>
        {['1', '2', '3', '+', '4', '5', '6', '-', '7', '8', '9', '*', '0', '=', '/'].map((value) => (
          <Button key={value} value={value} onClick={handleButtonClick} />
        ))}
      </div>
    </div>
  );
};

export default Calculator;