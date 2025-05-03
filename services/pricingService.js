const axios = require('axios');

const API_URL = 'https://customer.acecloudhosting.com/api/v1/pricing?is_gpu=true&resource=instances&region=ap-south-mum-1';

exports.fetchPricing = async () => {
  const response = await axios.get(API_URL);
//   console.log(response);
  return response.data;
};

