import axios from 'axios';

export class OpenAI {
  private static API_KEY = process.env.REACT_APP_OPENAI_API_KEY;
  private static API_URL = 'https://api.openai.com/v1';

  static async generateResponse(prompt: string): Promise<string> {
    try {
      const response = await axios.post(
        `${this.API_URL}/chat/completions`,
        {
          model: "gpt-4",
          messages: [{ role: "user", content: prompt }],
          temperature: 0.7,
        },
        {
          headers: {
            'Authorization': `Bearer ${this.API_KEY}`,
            'Content-Type': 'application/json',
          },
        }
      );
      return response.data.choices[0].message.content;
    } catch (error) {
      console.error('OpenAI API 오류:', error);
      throw error;
    }
  }

  static async generateSpeech(text: string): Promise<ArrayBuffer> {
    try {
      const response = await axios.post(
        `${this.API_URL}/audio/speech`,
        {
          model: "tts-1",
          input: text,
          voice: "shimmer",
        },
        {
          headers: {
            'Authorization': `Bearer ${this.API_KEY}`,
            'Content-Type': 'application/json',
          },
          responseType: 'arraybuffer',
        }
      );
      return response.data;
    } catch (error) {
      console.error('OpenAI TTS API 오류:', error);
      throw error;
    }
  }

  static async analyzeDiscussion(transcript: string): Promise<string> {
    const prompt = `
      다음 독서토론 내용을 분석해주세요:
      ${transcript}
      
      다음 항목을 포함해서 분석해주세요:
      1. 주요 논점
      2. 각 참여자의 기여도
      3. 토론의 깊이와 질
      4. 개선점 제안
    `;

    return this.generateResponse(prompt);
  }
} 