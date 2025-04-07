import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import styled from '@emotion/styled';
import DiscussionRegister from './pages/DiscussionRegister';
import DiscussionSearch from './pages/DiscussionSearch';
import TimerPage from './pages/TimerPage';

const AppContainer = styled.div`
  min-height: 100vh;
  background-color: #f8fafc;
`;

const Header = styled.header`
  background-color: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  padding: 1rem 2rem;
`;

const Nav = styled.nav`
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const Logo = styled.div`
  font-size: 1.5rem;
  font-weight: bold;
  color: #3b82f6;
`;

const NavLinks = styled.div`
  display: flex;
  gap: 2rem;
`;

const NavLink = styled(Link)`
  color: #4b5563;
  text-decoration: none;
  font-weight: 500;
  padding: 0.5rem 0;
  position: relative;
  
  &:hover {
    color: #3b82f6;
  }
  
  &::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    width: 0;
    height: 2px;
    background-color: #3b82f6;
    transition: width 0.3s ease;
  }
  
  &:hover::after {
    width: 100%;
  }
`;

const Footer = styled.footer`
  background-color: #1f2937;
  color: white;
  padding: 2rem;
  text-align: center;
`;

const App: React.FC = () => {
  return (
    <Router>
      <AppContainer>
        <Header>
          <Nav>
            <Logo>📚 독서토론 관리</Logo>
            <NavLinks>
              <NavLink to="/">독서 토론 등록</NavLink>
              <NavLink to="/search">독서 토론 검색</NavLink>
              <NavLink to="/timer">토론 타이머</NavLink>
            </NavLinks>
          </Nav>
        </Header>
        
        <Routes>
          <Route path="/" element={<DiscussionRegister />} />
          <Route path="/search" element={<DiscussionSearch />} />
          <Route path="/timer" element={<TimerPage />} />
        </Routes>
        
        <Footer>
          <p>© 2023 독서토론 관리 시스템. All rights reserved.</p>
        </Footer>
      </AppContainer>
    </Router>
  );
};

export default App; 