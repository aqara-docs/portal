import React, { useState, useEffect, useRef } from 'react';
import styled from '@emotion/styled';
import { OpenAI } from '../../services/openai';
import { Character } from '../../types/timer';
import { SpeechRecognition, SpeechRecognitionEvent } from '../../types/speech';

const TimerContainer = styled.div`
  background: white;
  border-radius: 10px;
  padding: 2rem;
  margin-bottom: 2rem;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
`;

const TimeDisplay = styled.div`
  font-size: 4rem;
  font-weight: bold;
  text-align: center;
  color: ${props => props.color || '#1f2937'};
  margin: 2rem 0;
`;

const ControlButton = styled.button<{ variant?: 'start' | 'stop' | 'reset' }>`
  padding: 1rem 2rem;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  margin: 0 0.5rem;
  transition: all 0.3s ease;

  ${props => {
    switch (props.variant) {
      case 'start':
        return `
          background: #10b981;
          color: white;
          &:hover { background: #059669; }
        `;
      case 'stop':
        return `
          background: #ef4444;
          color: white;
          &:hover { background: #dc2626; }
        `;
      case 'reset':
        return `
          background: #6b7280;
          color: white;
          &:hover { background: #4b5563; }
        `;
      default:
        return `
          background: #e5e7eb;
          color: #1f2937;
          &:hover { background: #d1d5db; }
        `;
    }
  }}
`;

const TranscriptArea = styled.textarea`
  width: 100%;
  height: 150px;
  margin: 1rem 0;
  padding: 1rem;
  border: 2px solid #e2e8f0;
  border-radius: 8px;
  resize: vertical;
  font-family: inherit;

  &:focus {
    border-color: #3b82f6;
    outline: none;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }
`;

const AnalysisCard = styled.div`
  background: #f8fafc;
  border-radius: 8px;
  padding: 1.5rem;
  margin-top: 1rem;
`;

const CharacterInfo = styled.div`
  margin-bottom: 1rem;
`;

const SpecialEffect = styled.span`
  font-weight: bold;
`;

const ExtraTurns = styled.span`
  font-weight: bold;
`;

const ControlPanel = styled.div`
  text-align: center;
  margin-bottom: 2rem;
`;

const TranscriptSection = styled.div`
  margin-bottom: 2rem;
`;

interface TimerProps {
  initialTime: number;
  character?: Character;
  onFinish: () => void;
}

const Timer: React.FC<TimerProps> = ({ initialTime, character, onFinish }) => {
  const [time, setTime] = useState(initialTime);
  const [isRunning, setIsRunning] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [analysis, setAnalysis] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [extraTime, setExtraTime] = useState(0);
  const [extraTurns, setExtraTurns] = useState(0);
  const intervalRef = useRef<NodeJS.Timeout>();
  const audioRef = useRef<HTMLAudioElement>(null);
  const speechRecognitionRef = useRef<SpeechRecognition | null>(null);

  useEffect(() => {
    // 특수 효과 적용
    if (character?.specialEffect) {
      switch (character.specialEffect) {
        case '시간 +1분':
          setExtraTime(60);
          break;
        case '발언권 2회':
          setExtraTurns(1);
          break;
        // 다른 특수 효과들도 추가 가능
      }
    }

    // Web Speech API 초기화
    if ('webkitSpeechRecognition' in window) {
      const SpeechRecognition = window.webkitSpeechRecognition;
      speechRecognitionRef.current = new SpeechRecognition();
      speechRecognitionRef.current.continuous = true;
      speechRecognitionRef.current.interimResults = true;
      speechRecognitionRef.current.lang = 'ko-KR';

      speechRecognitionRef.current.onresult = (event: SpeechRecognitionEvent) => {
        const transcript = Array.from(event.results)
          .map(result => result[0].transcript)
          .join('');
        setTranscript(prev => prev + ' ' + transcript);
      };
    }

    return () => {
      if (speechRecognitionRef.current) {
        speechRecognitionRef.current.stop();
      }
    };
  }, [character]);

  useEffect(() => {
    if (isRunning && time > 0) {
      intervalRef.current = setInterval(() => {
        setTime(prev => prev - 1);
      }, 1000);
    } else if (time === 0) {
      handleTimeUp();
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isRunning, time]);

  const handleTimeUp = async () => {
    setIsRunning(false);
    if (extraTurns > 0) {
      setExtraTurns(prev => prev - 1);
      setTime(initialTime);
      playNotification('추가 발언 기회가 있습니다.');
    } else {
      playTimeUpSound();
      await analyzeDiscussion();
      onFinish();
    }
  };

  const startTimer = () => {
    setIsRunning(true);
    if (speechRecognitionRef.current) {
      speechRecognitionRef.current.start();
    }
  };

  const stopTimer = () => {
    setIsRunning(false);
    if (speechRecognitionRef.current) {
      speechRecognitionRef.current.stop();
    }
  };

  const resetTimer = () => {
    setIsRunning(false);
    setTime(initialTime + extraTime);
    setTranscript('');
    if (speechRecognitionRef.current) {
      speechRecognitionRef.current.stop();
    }
  };

  const playTimeUpSound = async () => {
    try {
      const text = `${character?.name}님의 시간이 종료되었습니다.`;
      const audioData = await OpenAI.generateSpeech(text);
      const blob = new Blob([audioData], { type: 'audio/mp3' });
      const url = URL.createObjectURL(blob);
      setAudioUrl(url);
      if (audioRef.current) {
        audioRef.current.play();
      }
    } catch (error) {
      console.error('음성 생성 오류:', error);
    }
  };

  const analyzeDiscussion = async () => {
    if (!transcript.trim()) {
      alert('토론 내용을 입력해주세요.');
      return;
    }

    setIsAnalyzing(true);
    try {
      const result = await OpenAI.analyzeDiscussion(transcript);
      setAnalysis(result);
    } catch (error) {
      console.error('분석 오류:', error);
      alert('분석 중 오류가 발생했습니다.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const playNotification = async (message: string) => {
    try {
      const audioData = await OpenAI.generateSpeech(message);
      const blob = new Blob([audioData], { type: 'audio/mp3' });
      const url = URL.createObjectURL(blob);
      setAudioUrl(url);
      if (audioRef.current) {
        audioRef.current.play();
      }
    } catch (error) {
      console.error('음성 알림 오류:', error);
    }
  };

  return (
    <TimerContainer>
      <TimeDisplay color={time < 30 ? '#ef4444' : undefined}>
        {formatTime(time)}
      </TimeDisplay>

      {character && (
        <CharacterInfo>
          <h3>{character.name}</h3>
          <p>역할: {character.role}</p>
          <p>능력: {character.ability}</p>
          {character.specialEffect && (
            <SpecialEffect>특수효과: {character.specialEffect}</SpecialEffect>
          )}
          {extraTurns > 0 && (
            <ExtraTurns>남은 추가 발언: {extraTurns}회</ExtraTurns>
          )}
        </CharacterInfo>
      )}

      <ControlPanel>
        <ControlButton variant="start" onClick={startTimer} disabled={isRunning}>
          시작
        </ControlButton>
        <ControlButton variant="stop" onClick={stopTimer} disabled={!isRunning}>
          일시정지
        </ControlButton>
        <ControlButton variant="reset" onClick={resetTimer}>
          초기화
        </ControlButton>
      </ControlPanel>

      <TranscriptSection>
        <h3>토론 내용 (음성 인식 중...)</h3>
        <TranscriptArea
          value={transcript}
          onChange={(e) => setTranscript(e.target.value)}
          placeholder="토론 내용이 여기에 기록됩니다..."
          readOnly={isRunning}
        />
      </TranscriptSection>

      {analysis && (
        <AnalysisCard>
          <h3>AI 분석 결과</h3>
          <div style={{ whiteSpace: 'pre-line' }}>{analysis}</div>
        </AnalysisCard>
      )}

      <audio ref={audioRef} src={audioUrl || ''} />
    </TimerContainer>
  );
};

export default Timer; 