import React, { useState } from 'react';
import styled from '@emotion/styled';
import Timer from '../components/Timer/Timer';
import OrderPicker from '../components/Timer/OrderPicker';
import { Character } from '../types/timer';

const PageContainer = styled.div`
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
`;

const SettingsCard = styled.div`
  background: white;
  border-radius: 10px;
  padding: 2rem;
  margin-bottom: 2rem;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
`;

const Select = styled.select`
  width: 100%;
  padding: 0.75rem;
  border: 2px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 1rem;
  font-size: 1rem;

  &:focus {
    border-color: #3b82f6;
    outline: none;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }
`;

const Label = styled.label`
  display: block;
  margin-bottom: 0.5rem;
  color: #4b5563;
  font-weight: 500;
`;

const TimerPage: React.FC = () => {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [currentCharacterIndex, setCurrentCharacterIndex] = useState(0);
  const [timePerPerson, setTimePerPerson] = useState(180); // 3분

  const handleOrderChange = (newCharacters: Character[]) => {
    setCharacters(newCharacters);
    setCurrentCharacterIndex(0);
  };

  const handleFinish = () => {
    if (currentCharacterIndex < characters.length - 1) {
      setCurrentCharacterIndex(prev => prev + 1);
    }
  };

  const handleTimeChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setTimePerPerson(parseInt(event.target.value));
  };

  return (
    <PageContainer>
      <h1>토론 타이머</h1>

      <SettingsCard>
        <Label htmlFor="timeSelect">발언 시간 설정</Label>
        <Select
          id="timeSelect"
          value={timePerPerson}
          onChange={handleTimeChange}
        >
          <option value={60}>1분</option>
          <option value={120}>2분</option>
          <option value={180}>3분</option>
          <option value={240}>4분</option>
          <option value={300}>5분</option>
        </Select>
      </SettingsCard>

      <OrderPicker onOrderChange={handleOrderChange} />

      {characters.length > 0 && (
        <Timer
          initialTime={timePerPerson}
          character={characters[currentCharacterIndex]}
          onFinish={handleFinish}
        />
      )}

      {characters.length > 0 && (
        <SettingsCard>
          <h3>현재 순서</h3>
          <p>
            {currentCharacterIndex + 1} / {characters.length}:&nbsp;
            {characters[currentCharacterIndex].name}
            ({characters[currentCharacterIndex].role})
          </p>
        </SettingsCard>
      )}
    </PageContainer>
  );
};

export default TimerPage; 