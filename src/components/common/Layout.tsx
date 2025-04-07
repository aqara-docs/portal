import React from 'react';
import styled from '@emotion/styled';
import Navbar from './Navbar';

const Container = styled.div`
  min-height: 100vh;
  background: #f5f6fa;
`;

const Content = styled.main`
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
`;

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  return (
    <Container>
      <Navbar />
      <Content>{children}</Content>
    </Container>
  );
};

export default Layout; 