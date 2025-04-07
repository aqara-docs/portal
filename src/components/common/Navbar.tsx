import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import styled from '@emotion/styled';

const Nav = styled.nav`
  background: #2c3e50;
  padding: 1rem;
`;

const NavLink = styled(Link)<{ active: boolean }>`
  color: ${props => props.active ? '#fff' : '#bdc3c7'};
  text-decoration: none;
  padding: 0.5rem 1rem;
  margin: 0 0.5rem;
  border-radius: 4px;
  transition: all 0.3s ease;

  &:hover {
    background: #34495e;
    color: #fff;
  }
`;

const Navbar: React.FC = () => {
  const location = useLocation();

  return (
    <Nav>
      <NavLink to="/" active={location.pathname === '/'}>
        독서토론 등록
      </NavLink>
      <NavLink to="/search" active={location.pathname === '/search'}>
        독서토론 검색
      </NavLink>
      <NavLink to="/timer" active={location.pathname === '/timer'}>
        토론 순서/타이머
      </NavLink>
    </Nav>
  );
};

export default Navbar; 