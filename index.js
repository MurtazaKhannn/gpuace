const express = require('express');
const app = express();
const port = 3000;
const pricingRoutes = require('./routes/pricingRoutes.js');
// const cors = require('cors');

// Root route
app.get('/', (req, res) => {
  res.send('Hello, world!');
});

app.use('/api/pricing', pricingRoutes);

// Start server
app.listen(port, () => {
  console.log(`Server is running at PORT : ${port}`);
});