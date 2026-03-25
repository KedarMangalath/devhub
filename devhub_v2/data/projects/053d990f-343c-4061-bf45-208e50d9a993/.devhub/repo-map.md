# Repo Map: My awesome calculatior

- Fingerprint: 8e3e8e5bbb3847a263b8a5f22e38a5e2d4b3d370
- Indexed files: 9

## Top Directories
- `.`: 4 files
- `src`: 3 files
- `backend`: 2 files

## Important Files
- `src/App.js`: src/App.js is a javascript file with about 15 lines. Primary symbol: App. Key imports: import React from 'react';, import { BrowserRouter as Router, Route, Switch } from 'react-router-dom';, import Calculator from './components/Calculator';. Routes/endpoints: /. Likely role: api.
- `backend/urls.py`: backend/urls.py is a python file with about 6 lines. Key imports: from django.urls import path, from .views import calculate. Routes/endpoints: api/calculate. Likely role: api.
- `backend/views.py`: backend/views.py is a python file with about 16 lines. Primary symbol: calculate. Key imports: from rest_framework.decorators import api_view, from rest_framework.response import Response, from rest_framework import status, import sympy as sp, import html. Likely role: routing.
- `src/components/Button.js`: src/components/Button.js is a javascript file with about 9 lines. Primary symbol: Button. Key imports: import React from 'react';. Likely role: ui.
- `src/components/Calculator.js`: src/components/Calculator.js is a javascript file with about 47 lines. Primary symbol: Calculator. Key imports: import React, { useState } from 'react';, import Button from './Button';, import axios from 'axios';. Likely role: ui.
- `README.md`: README.md is a markdown file with about 8 lines. Likely role: docs, config.
- `app.js`: app.js is a javascript file with about 5 lines. Key imports: import React from 'react';, import ReactDOM from 'react-dom';, import App from './App';.
- `index.html`: index.html is a html file with about 26 lines.
- `styles.css`: styles.css is a css file with about 38 lines.

## Detected Routes
- `/`
- `api/calculate`

## Repo Tree
```text
My awesome calculatior/
|- backend
|  |- urls.py
|  `- views.py
|- src
|  |- components
|  |  |- Button.js
|  |  `- Calculator.js
|  `- App.js
|- app.js
|- index.html
|- README.md
`- styles.css
```