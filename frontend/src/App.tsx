import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { InsightFeed } from './components/InsightFeed';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<InsightFeed />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
