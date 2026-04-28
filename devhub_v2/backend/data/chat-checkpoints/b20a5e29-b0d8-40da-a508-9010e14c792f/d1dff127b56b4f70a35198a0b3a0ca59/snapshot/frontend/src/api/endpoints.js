import client from './client'

export const login = async (credentials) => {
  // FastAPI OAuth2PasswordBearer requires application/x-www-form-urlencoded
  const formData = new URLSearchParams();
  formData.append('username', credentials.username || credentials.email);
  formData.append('password', credentials.password);

  const response = await client.post('/auth/login', formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
  return response.data;
};

export const getSpecialties = async () => {
  const response = await client.get('/specialties');
  return response.data;
};

export const getDoctors = async (params) => {
  const response = await client.get('/doctors', { params });
  return response.data;
};

export const getDoctor = async (id) => {
  const response = await client.get(`/doctors/${id}`);
  return response.data;
};

export const getDoctorSlots = async (id) => {
  const response = await client.get(`/doctors/${id}/slots`);
  return response.data;
};

export const createAppointment = async (data) => {
  const response = await client.post('/appointments', data);
  return response.data;
};

export const getAppointments = async () => {
  const response = await client.get('/appointments');
  return response.data;
};

export const getPrescriptions = async () => {
  const response = await client.get('/prescriptions');
  return response.data;
};

export const createPrescription = async (data) => {
  const response = await client.post('/prescriptions', data);
  return response.data;
};

export const getMedicines = async () => {
  const response = await client.get('/medicines');
  return response.data;
};

export const createOrder = async (data) => {
  const response = await client.post('/orders', data);
  return response.data;
};