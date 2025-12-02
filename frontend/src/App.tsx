import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { UnifiedFeed } from './components/UnifiedFeed';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<UnifiedFeed />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
