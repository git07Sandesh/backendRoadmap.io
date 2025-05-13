import express from "express";
import { createPath } from "../controllers/path.controller.js";

const router = express.Router();

router.post("/", createPath);

export default router;