import React, { useState } from 'react';
import styled from '@emotion/styled';
import { Character } from '../../types/timer';
import { OpenAI } from '../../services/openai';

const Container = styled.div`
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
`;

const Card = styled.div`
  background: white;
  border-radius: 10px;
  padding: 2rem;
  margin-bottom: 2rem;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
`;

const CharacterCard = styled.div<{ role: string }>`
  background: #f8f9fa;
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 1rem;
  border-left: 5px solid ${props => {
    switch (props.role) {
      case '발표자': return '#3b82f6';
      case '질문자': return '#10b981';
      case '토론자': return '#f59e0b';
      default: return '#6b7280';
    }
  }};
  transition: all 0.3s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }
`;

const Input = styled.input`
  width: 100%;
  padding: 1rem;
  border: 2px solid #e2e8f0;
  border-radius: 8px;
  font-size: 1rem;
  margin-bottom: 1rem;

  &:focus {
    border-color: #3b82f6;
    outline: none;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }
`;

const Button = styled.button<{ primary?: boolean; loading?: boolean }>`
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: ${props => props.loading ? 'wait' : 'pointer'};
  opacity: ${props => props.loading ? 0.7 : 1};
  transition: all 0.3s ease;
  margin-right: 1rem;
  
  ${props => props.primary ? `
    background: #3b82f6;
    color: white;
    &:hover { background: #2563eb; }
  ` : `
    background: #e2e8f0;
    color: #1f2937;
    &:hover { background: #cbd5e1; }
  `}
`;

const Title = styled.h2`
  color: #1f2937;
  margin-bottom: 1.5rem;
  font-size: 1.8rem;
`;

const Subtitle = styled.h3`
  color: #4b5563;
  margin-bottom: 1rem;
  font-size: 1.2rem;
`;

const LoadingSpinner = styled.div`
  display: inline-block;
  width: 20px;
  height: 20px;
  border: 3px solid #f3f3f3;
  border-top: 3px solid #3498db;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-right: 8px;

  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
`;

const SpecialEffect = styled.span`
  color: #ef4444;
  font-weight: 600;
`;

const AbilityText = styled.span`
  color: #059669;
  font-weight: 500;
`;

interface OrderPickerProps {
  onOrderChange: (characters: Character[]) => void;
}

const OrderPicker: React.FC<OrderPickerProps> = ({ onOrderChange }) => {
  const [participants, setParticipants] = useState<string>('');
  const [orderedList, setOrderedList] = useState<Character[]>([]);
  const [aiSuggestion, setAiSuggestion] = useState<string>('');
  const [loading, setLoading] = useState(false);

  const generateOrder = async () => {
    const names = participants.split(',').map(name => name.trim()).filter(Boolean);
    if (names.length === 0) {
      alert('참여자 이름을 입력해주세요.');
      return;
    }

    setLoading(true);
    try {
      const prompt = `
독서토론 참여자들의 역할과 능력을 배정해주세요. 창의적이고 재미있게 작성해주세요.
참여자: ${names.join(', ')}

각 참여자에게 다음을 배정해주세요:
1. 역할 (발표자, 질문자, 토론자 중 하나)
2. 특별한 능력 (예: 논리적 분석, 창의적 해석, 감정적 공감 등)
3. 특수효과 (시간 +1분, 발언권 2회, 우선 발언 중 하나)

다음 형식으로 응답해주세요:
이름1:
- 역할: [역할]
- 능력: [능력]
- 특수효과: [특수효과]

이름2:
...
      `;

      const aiResponse = await OpenAI.generateResponse(prompt);
      const aiCharacters = parseAIResponse(aiResponse, names);
      
      setOrderedList(aiCharacters);
      onOrderChange(aiCharacters);
      
      const suggestionPrompt = `
위 참여자들의 역할을 고려하여, 효과적인 토론 진행 방법을 제안해주세요.
각 참여자의 능력을 최대한 활용할 수 있는 방법도 포함해주세요.
      `;
      
      const suggestion = await OpenAI.generateResponse(suggestionPrompt);
      setAiSuggestion(suggestion);
    } catch (error) {
      console.error('AI 생성 오류:', error);
      const defaultCharacters = generateDefaultCharacters(names);
      setOrderedList(defaultCharacters);
      onOrderChange(defaultCharacters);
    } finally {
      setLoading(false);
    }
  };

  const parseAIResponse = (response: string, names: string[]): Character[] => {
    const characters: Character[] = [];
    const sections = response.split('\n\n');
    
    for (const section of sections) {
      if (!section.trim()) continue;
      
      const lines = section.split('\n');
      const name = lines[0].split(':')[0].trim();
      if (!names.includes(name)) continue;

      const role = lines.find(l => l.includes('역할:'))?.split(':')[1].trim() || '토론자';
      const ability = lines.find(l => l.includes('능력:'))?.split(':')[1].trim() || '일반 토론';
      const effect = lines.find(l => l.includes('특수효과:'))?.split(':')[1].trim() || '없음';

      characters.push({
        id: Math.random().toString(36).substr(2, 9),
        name,
        role,
        ability,
        specialEffect: effect
      });
    }

    return characters.length === names.length ? characters : generateDefaultCharacters(names);
  };

  // 기본 캐릭터 생성 함수 (AI 실패시 폴백)
  const generateDefaultCharacters = (names: string[]): Character[] => {
    const roles = ['발표자', '질문자', '토론자'];
    const abilities = ['명확한 설명', '깊이 있는 질문', '활발한 토론'];
    const effects = ['시간 +1분', '발언권 2회', '우선 발언'];

    return names
      .map(name => ({
        id: Math.random().toString(36).substr(2, 9),
        name,
        role: roles[Math.floor(Math.random() * roles.length)],
        ability: abilities[Math.floor(Math.random() * abilities.length)],
        specialEffect: effects[Math.floor(Math.random() * effects.length)]
      }))
      .sort(() => Math.random() - 0.5);
  };

  return (
    <Container>
      <Title>🎯 토론 순서 정하기</Title>
      
      <Card>
        <Subtitle>참여자 입력</Subtitle>
        <Input
          value={participants}
          onChange={(e) => setParticipants(e.target.value)}
          placeholder="참여자 이름을 쉼표(,)로 구분하여 입력해주세요"
          disabled={loading}
        />
        <Button primary onClick={generateOrder} disabled={loading}>
          {loading && <LoadingSpinner />}
          {loading ? 'AI가 역할을 배정하는 중...' : '🎲 순서 정하기'}
        </Button>
        <Button onClick={() => {
          setOrderedList([]);
          setAiSuggestion('');
          onOrderChange([]);
          setParticipants('');
        }}>
          초기화
        </Button>
      </Card>

      {aiSuggestion && (
        <Card>
          <Subtitle>🤖 AI의 토론 진행 제안</Subtitle>
          <p>{aiSuggestion}</p>
        </Card>
      )}

      {orderedList.length > 0 && (
        <Card>
          <Subtitle>📋 토론 순서</Subtitle>
          {orderedList.map((character, index) => (
            <CharacterCard key={character.id} role={character.role}>
              <h4>{index + 1}. {character.name}</h4>
              <p>역할: {character.role}</p>
              <p><AbilityText>능력: {character.ability}</AbilityText></p>
              <p><SpecialEffect>특수효과: {character.specialEffect}</SpecialEffect></p>
            </CharacterCard>
          ))}
        </Card>
      )}
    </Container>
  );
};

export default OrderPicker; 