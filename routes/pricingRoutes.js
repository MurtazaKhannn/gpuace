const express = require('express');
const router = express.Router();
const pricingController = require('../controllers/pricingController');

router.post('/', pricingController.getPricingData);

module.exports = router;
