import axios from "axios";

const API = "/api";

export const fetchIssues = () => axios.get(`${API}/analyze`);
export const runAction = (command, issue) =>
  axios.post(`${API}/execute`, { command, issue });
