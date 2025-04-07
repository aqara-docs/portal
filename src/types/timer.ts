export interface Character {
  id: string;
  name: string;
  role: string;
  ability: string;
  specialEffect: string;
}

export interface TimerSettings {
  duration: number;
  enableAlarm: boolean;
  alarmType: 'beep' | 'voice';
}

export interface OrderResult {
  characters: Character[];
  specialEffect: string;
}

export interface TimerProps {
  initialTime: number;
  character?: Character;
} 