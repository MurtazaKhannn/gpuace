const pricingService = require('../services/pricingService.js');
const { prefilteredGPUs } = require('../services/prefilterGPU.js')

exports.getPricingData = async (req, res) => {
  try {
    const data = await pricingService.fetchPricing();
    // console.log(data.data.length);
    const userInput = {
        "country": "india",
        "operating_system": "windows",
        "resource_class": "a100",
        "resource_name": "W.N.A100.96",
        "vcpus": 16,
        "ram": 96,
        "price_per_hour": 3.42,
        "price_per_month": 1563,
        "price_per_spot": 2.394,
        "currency": "USD",
        "is_gpu": 1,
        "is_spot": 0,
        "resource": "instances",
        "resource_type": "gpu",
        "region": "mumbai",
        "flavor_id": "773b990d-6c7e-41e7-a40d-601bbbcc6373",
        "gpu_description": "1x A100-80GB",
        "is_public": 1
    }
      
    const filtered = prefilteredGPUs(data.data, userInput);
    console.log(filtered.length);
    

    res.json(filtered);
  } catch (error) {
    console.error('Controller Error:', error.message);
    res.status(500).json({ error: 'Failed to retrieve pricing data' });
  }
};
