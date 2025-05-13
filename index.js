import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import pathRoute from './routes/path.route.js'


dotenv.config();
const app = express();


app.use(cors());
app.use(express.json())
app.use("/api/path", pathRoute)

const PORT = process.env.PORT || 3000;

app.listen(PORT,() => {
    console.log(`Server is running on port ${PORT}`)
})