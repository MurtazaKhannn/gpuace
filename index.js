const express = require('express');
const app = express();
const port = 3000;
const pricingRoutes = require('./routes/pricingRoutes.js');
const cors = require('cors');

app.use(express.json());


app.use(cors({
  origin: '*', // Allow all origins
  methods: ['GET', 'POST'], // Allow specific HTTP methods
//   allowedHeaders: ['Content-Type', 'Authorization'], // Allow specific headers
}));

// Root route
app.get('/', (req, res) => {
  res.send('Hello, world!');
});

app.use('/api/pricing', pricingRoutes);

// Start server
app.listen(port, () => {
  console.log(`Server is running at PORT : ${port}`);
});
