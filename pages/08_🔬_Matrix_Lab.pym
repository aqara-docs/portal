import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scipy import linalg, integrate, optimize, interpolate
import sympy as sp
from io import StringIO
from plotly.subplots import make_subplots
import re
import tempfile
import os
import subprocess
import sys

# 페이지 설정
st.set_page_config(
    page_title="Matrix Lab",
    page_icon="🔢",
    layout="wide"
)

def evaluate_matrix_expression(expr_str, variables):
    """행렬 수식 계산"""
    try:
        # 변수들을 locals에 추가
        local_dict = {**variables}
        # numpy 함수들을 locals에 추가
        local_dict.update({
            'np': np,
            'linalg': linalg,
            'inv': np.linalg.inv,
            'det': np.linalg.det,
            'eig': np.linalg.eig,
            'svd': np.linalg.svd,
            'norm': np.linalg.norm
        })
        
        # 수식 평가
        result = eval(expr_str, {"__builtins__": {}}, local_dict)
        return result
    except Exception as e:
        st.error(f"수식 계산 중 오류 발생: {str(e)}")
        return None

def parse_matrix_input(text):
    """행렬 입력 텍스트 파싱"""
    try:
        # 입력 텍스트를 StringIO로 변환하여 numpy loadtxt 사용
        text = text.replace('[', '').replace(']', '')
        matrix = np.loadtxt(StringIO(text))
        return matrix
    except Exception as e:
        st.error(f"행렬 입력 형식이 잘못되었습니다: {str(e)}")
        return None

def plot_matrix(matrix, title="행렬 시각화"):
    """행렬 히트맵 시각화"""
    fig = px.imshow(
        matrix,
        title=title,
        color_continuous_scale='RdBu',
        labels=dict(color="값")
    )
    st.plotly_chart(fig)

def plot_3d_surface(X, Y, Z, title="3D 표면"):
    """3D 표면 플롯"""
    fig = go.Figure(data=[go.Surface(z=Z, x=X, y=Y)])
    fig.update_layout(title=title, autosize=False, width=800, height=600)
    st.plotly_chart(fig)

def convert_matlab_to_python(matlab_code):
    """MATLAB/Octave 코드를 Python 코드로 변환"""
    # 기본 변환 규칙
    conversions = {
        r'(\w+)\s*=\s*zeros\((\d+),(\d+)\)': r'\1 = np.zeros((\2,\3))',
        r'(\w+)\s*=\s*ones\((\d+),(\d+)\)': r'\1 = np.ones((\2,\3))',
        r'(\w+)\s*=\s*eye\((\d+)\)': r'\1 = np.eye(\2)',
        r'(\w+)\s*=\s*rand\((\d+),(\d+)\)': r'\1 = np.random.rand(\2,\3)',
        r'disp\((.*?)\)': r'print(\1)',
        r'plot\((.*?),(.*?)\)': r'fig = plot(\1,\2)',
        r'title\((.*?)\)': r"plt.title(\1)",
        r'xlabel\((.*?)\)': r"plt.xlabel(\1)",
        r'ylabel\((.*?)\)': r"plt.ylabel(\1)",
        r'mesh\((.*?),(.*?),(.*?)\)': r'fig = mesh(\1,\2,\3)',
        r'(\w+)\'': r'\1.T',  # 전치 연산자
        r'(\w+)\.\*(\w+)': r'\1*\2',  # 요소별 곱셈
        r'(\w+)\.\/(\w+)': r'\1/\2',  # 요소별 나눗셈
        r'(\w+)\^(\d+)': r'np.power(\1,\2)',  # 거듭제곱
    }
    
    python_code = matlab_code
    for pattern, replacement in conversions.items():
        python_code = re.sub(pattern, replacement, python_code)
    
    return python_code

def run_octave_script(code):
    """Octave 스크립트 실행"""
    try:
        # Octave 설치 확인
        result = subprocess.run(['which', 'octave'], capture_output=True, text=True)
        if result.returncode != 0:
            return None, "Octave가 설치되어 있지 않습니다."
        
        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(suffix='.m', mode='w', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # Octave 실행
            result = subprocess.run(
                ['octave', '--no-gui', temp_file],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # 그래프 파일 확인
                if os.path.exists('figure1.png'):
                    st.image('figure1.png')
                    os.remove('figure1.png')
                return result.stdout, None
            else:
                return None, f"실행 오류: {result.stderr}"
        finally:
            os.unlink(temp_file)
            
    except Exception as e:
        return None, f"오류 발생: {str(e)}"

def numerical_derivative(f, x, h=1e-7):
    """수치 미분 (중앙 차분법)"""
    return (f(x + h) - f(x - h)) / (2 * h)

def symbolic_derivative(expr_str, var='x'):
    """기호 미분"""
    x = sp.Symbol(var)
    expr = sp.sympify(expr_str)
    return sp.diff(expr, x)

def main():
    st.title("🔢 Matrix Lab")
    st.write("행렬 계산과 수치 해석을 위한 도구")
    
    # 탭 생성
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "행렬 계산",
        "그래프 플로팅",
        "수치 해석",
        "선형 대수",
        "MATLAB/Octave"  # 새로운 탭 추가
    ])
    
    # 행렬 계산 탭
    with tab1:
        st.subheader("행렬 계산")
        
        col1, col2 = st.columns(2)
        
        with col1:
            matrix_a = st.text_area(
                "행렬 A 입력",
                "1 2 3\n4 5 6\n7 8 9",
                help="공백으로 구분된 행렬 입력 (예: 1 2 3\\n4 5 6\\n7 8 9)"
            )
            
            A = parse_matrix_input(matrix_a)
            if A is not None:
                st.write("행렬 A:")
                st.write(A)
                plot_matrix(A, "행렬 A 시각화")
        
        with col2:
            matrix_b = st.text_area(
                "행렬 B 입력",
                "9 8 7\n6 5 4\n3 2 1",
                help="공백으로 구분된 행렬 입력"
            )
            
            B = parse_matrix_input(matrix_b)
            if B is not None:
                st.write("행렬 B:")
                st.write(B)
                plot_matrix(B, "행렬 B 시각화")
        
        if A is not None and B is not None:
            operation = st.selectbox(
                "연산 선택",
                [
                    "A + B", "A - B", "A × B", "A ÷ B",
                    "det(A)", "inv(A)", "eig(A)",
                    "svd(A)", "norm(A)"
                ]
            )
            
            if st.button("계산"):
                variables = {'A': A, 'B': B}
                
                if operation == "A + B":
                    result = evaluate_matrix_expression("A + B", variables)
                elif operation == "A - B":
                    result = evaluate_matrix_expression("A - B", variables)
                elif operation == "A × B":
                    result = evaluate_matrix_expression("A @ B", variables)
                elif operation == "A ÷ B":
                    result = evaluate_matrix_expression("A @ np.linalg.inv(B)", variables)
                elif operation == "det(A)":
                    result = evaluate_matrix_expression("np.linalg.det(A)", variables)
                elif operation == "inv(A)":
                    result = evaluate_matrix_expression("np.linalg.inv(A)", variables)
                elif operation == "eig(A)":
                    eigenvals, eigenvecs = evaluate_matrix_expression("np.linalg.eig(A)", variables)
                    st.write("고유값:", eigenvals)
                    st.write("고유벡터:", eigenvecs)
                    return
                elif operation == "svd(A)":
                    U, s, Vh = evaluate_matrix_expression("np.linalg.svd(A)", variables)
                    st.write("U:", U)
                    st.write("특이값:", s)
                    st.write("V^H:", Vh)
                    return
                elif operation == "norm(A)":
                    result = evaluate_matrix_expression("np.linalg.norm(A)", variables)
                
                if result is not None:
                    st.write("결과:")
                    st.write(result)
                    if isinstance(result, np.ndarray) and result.ndim == 2:
                        plot_matrix(result, "결과 행렬 시각화")
    
    # 그래프 플로팅 탭
    with tab2:
        st.subheader("그래프 플로팅")
        
        plot_type = st.selectbox(
            "플롯 유형",
            ["2D 함수", "3D 표면", "등고선"]
        )
        
        if plot_type == "2D 함수":
            x_range = st.slider("x 범위", -10.0, 10.0, (-5.0, 5.0))
            func_str = st.text_input("함수 입력 (x 변수 사용)", "np.sin(x)")
            
            x = np.linspace(x_range[0], x_range[1], 200)
            try:
                y = eval(func_str, {"np": np, "x": x})
                fig = px.line(x=x, y=y, title="함수 그래프")
                st.plotly_chart(fig)
            except Exception as e:
                st.error(f"함수 계산 중 오류 발생: {str(e)}")
        
        elif plot_type in ["3D 표면", "등고선"]:
            x_range = st.slider("x 범위", -10.0, 10.0, (-5.0, 5.0))
            y_range = st.slider("y 범위", -10.0, 10.0, (-5.0, 5.0))
            func_str = st.text_input(
                "함수 입력 (x, y 변수 사용)",
                "np.sin(np.sqrt(x**2 + y**2))"
            )
            
            x = np.linspace(x_range[0], x_range[1], 100)
            y = np.linspace(y_range[0], y_range[1], 100)
            X, Y = np.meshgrid(x, y)
            
            try:
                Z = eval(func_str, {"np": np, "x": X, "y": Y})
                
                if plot_type == "3D 표면":
                    plot_3d_surface(X, Y, Z)
                else:
                    fig = px.contour(
                        x=x, y=y, z=Z,
                        title="등고선 그래프"
                    )
                    st.plotly_chart(fig)
            except Exception as e:
                st.error(f"함수 계산 중 오류 발생: {str(e)}")
    
    # 수치 해석 탭
    with tab3:
        st.subheader("수치 해석")
        
        analysis_type = st.selectbox(
            "분석 유형",
            ["미분", "적분", "방정식 풀이", "최적화", "보간/근사"]
        )
        
        if analysis_type == "미분":
            st.write("### 함수의 미분")
            
            diff_method = st.radio(
                "미분 방법",
                ["기호적 미분", "수치 미분"]
            )
            
            func_str = st.text_input(
                "함수 입력 (x 변수 사용)",
                "x**2"
            )
            
            if diff_method == "기호적 미분":
                try:
                    derivative = symbolic_derivative(func_str)
                    st.write(f"도함수: {derivative}")
                    
                    # 그래프로 시각화
                    x = np.linspace(-5, 5, 100)
                    x_sym = sp.Symbol('x')
                    f = sp.lambdify(x_sym, sp.sympify(func_str))
                    df = sp.lambdify(x_sym, derivative)
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=x, y=f(x), name='원함수'))
                    fig.add_trace(go.Scatter(x=x, y=df(x), name='도함수'))
                    fig.update_layout(title='함수와 도함수')
                    st.plotly_chart(fig)
                    
                except Exception as e:
                    st.error(f"미분 계산 중 오류 발생: {str(e)}")
            
            else:  # 수치 미분
                try:
                    f = lambda x: eval(func_str, {"np": np, "x": x})
                    x0 = st.number_input("미분할 위치", value=0.0)
                    result = numerical_derivative(f, x0)
                    st.write(f"x = {x0}에서의 미분값: {result:.6f}")
                except Exception as e:
                    st.error(f"수치 미분 계산 중 오류 발생: {str(e)}")
        
        elif analysis_type == "적분":
            st.write("### 함수의 적분")
            
            func_str = st.text_input(
                "함수 입력 (x 변수 사용)",
                "x**2"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                a = st.number_input("적분 구간 시작", value=-1.0)
            with col2:
                b = st.number_input("적분 구간 끝", value=1.0)
            
            try:
                f = lambda x: eval(func_str, {"np": np, "x": x})
                result, error = integrate.quad(f, a, b)
                st.write(f"정적분 결과: {result:.6f} (오차: {error:.2e})")
                
                # 적분 시각화
                x = np.linspace(min(a-1, a), max(b+1, b), 200)
                y = f(x)
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=x, y=y, name='함수'))
                
                # 적분 영역 채우기
                x_fill = np.linspace(a, b, 100)
                y_fill = f(x_fill)
                fig.add_trace(go.Scatter(
                    x=x_fill,
                    y=y_fill,
                    fill='tozeroy',
                    name='적분 영역'
                ))
                
                fig.update_layout(title='적분 영역 시각화')
                st.plotly_chart(fig)
                
            except Exception as e:
                st.error(f"적분 계산 중 오류 발생: {str(e)}")
        
        elif analysis_type == "방정식 풀이":
            st.write("### 방정식 풀이")
            
            eq_type = st.radio(
                "방정식 유형",
                ["일반 방정식", "연립 방정식"]
            )
            
            if eq_type == "일반 방정식":
                func_str = st.text_input(
                    "방정식 입력 (좌변만, x 변수 사용)",
                    "x**2 - 4"
                )
                
                try:
                    f = lambda x: eval(func_str, {"np": np, "x": x})
                    x0 = st.number_input("초기값", value=1.0)
                    
                    result = optimize.root_scalar(f, x0=x0)
                    if result.converged:
                        st.write(f"해: {result.root:.6f}")
                        
                        # 함수 그래프 시각화
                        x = np.linspace(result.root-2, result.root+2, 200)
                        y = f(x)
                        
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(x=x, y=y, name='함수'))
                        fig.add_trace(go.Scatter(
                            x=[result.root],
                            y=[0],
                            mode='markers',
                            name='해',
                            marker=dict(size=10)
                        ))
                        fig.update_layout(title='방정식의 해')
                        st.plotly_chart(fig)
                    else:
                        st.error("해를 찾지 못했습니다.")
                except Exception as e:
                    st.error(f"방정식 풀이 중 오류 발생: {str(e)}")
            
            else:  # 연립 방정식
                st.write("연립 방정식 형태: F(x, y) = 0, G(x, y) = 0")
                f_str = st.text_input("F(x, y) = ", "x**2 + y**2 - 1")
                g_str = st.text_input("G(x, y) = ", "y - x")
                
                try:
                    F = lambda vars: [
                        eval(f_str, {"np": np, "x": vars[0], "y": vars[1]}),
                        eval(g_str, {"np": np, "x": vars[0], "y": vars[1]})
                    ]
                    
                    result = optimize.root(F, [1.0, 1.0])
                    if result.success:
                        st.write(f"해: x = {result.x[0]:.6f}, y = {result.x[1]:.6f}")
                    else:
                        st.error("해를 찾지 못했습니다.")
                except Exception as e:
                    st.error(f"연립 방정식 풀이 중 오류 발생: {str(e)}")
        
        elif analysis_type == "최적화":
            st.write("### 함수 최적화")
            
            func_str = st.text_input(
                "목적 함수 입력 (x 변수 사용)",
                "(x - 2)**2 + 4"
            )
            
            try:
                f = lambda x: eval(func_str, {"np": np, "x": x})
                x0 = st.number_input("초기값", value=0.0)
                
                result = optimize.minimize_scalar(f, x0)
                if result.success:
                    st.write(f"최솟값: {result.fun:.6f} (x = {result.x:.6f})")
                    
                    # 최적화 결과 시각화
                    x = np.linspace(result.x-2, result.x+2, 200)
                    y = f(x)
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=x, y=y, name='함수'))
                    fig.add_trace(go.Scatter(
                        x=[result.x],
                        y=[result.fun],
                        mode='markers',
                        name='최솟값',
                        marker=dict(size=10)
                    ))
                    fig.update_layout(title='함수의 최솟값')
                    st.plotly_chart(fig)
                else:
                    st.error("최적화에 실패했습니다.")
            except Exception as e:
                st.error(f"최적화 중 오류 발생: {str(e)}")
        
        elif analysis_type == "보간/근사":
            st.write("### 데이터 보간/근사")
            
            # 데이터 입력
            x_data = st.text_input("x 좌표 (쉼표로 구분)", "1, 2, 3, 4, 5")
            y_data = st.text_input("y 좌표 (쉼표로 구분)", "2.1, 3.8, 7.2, 13.5, 26.0")
            
            try:
                x = np.array([float(x.strip()) for x in x_data.split(',')])
                y = np.array([float(y.strip()) for y in y_data.split(',')])
                
                method = st.selectbox(
                    "보간/근사 방법",
                    ["선형 보간", "3차 스플라인 보간", "다항식 근사"]
                )
                
                if method == "선형 보간":
                    f = interpolate.interp1d(x, y)
                elif method == "3차 스플라인 보간":
                    f = interpolate.CubicSpline(x, y)
                else:  # 다항식 근사
                    degree = st.slider("다항식 차수", 1, 5, 2)
                    coef = np.polyfit(x, y, degree)
                    f = np.poly1d(coef)
                
                # 결과 시각화
                x_new = np.linspace(min(x), max(x), 200)
                y_new = f(x_new)
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=x, y=y,
                    mode='markers',
                    name='원본 데이터'
                ))
                fig.add_trace(go.Scatter(
                    x=x_new, y=y_new,
                    name='보간/근사 함수'
                ))
                fig.update_layout(title=f'{method} 결과')
                st.plotly_chart(fig)
                
            except Exception as e:
                st.error(f"보간/근사 중 오류 발생: {str(e)}")
    
    # 선형 대수 탭
    with tab4:
        st.subheader("선형 대수")
        
        analysis_type = st.selectbox(
            "분석 유형",
            ["고유값/고유벡터", "행렬 분해", "선형 시스템", "벡터 공간"]
        )
        
        if analysis_type == "고유값/고유벡터":
            st.write("### 고유값과 고유벡터 계산")
            
            matrix = st.text_area(
                "행렬 입력",
                "1 2 3\n4 5 6\n7 8 9",
                help="공백으로 구분된 행렬 입력"
            )
            
            A = parse_matrix_input(matrix)
            if A is not None:
                try:
                    eigenvals, eigenvecs = np.linalg.eig(A)
                    
                    st.write("#### 고유값:")
                    for i, ev in enumerate(eigenvals):
                        st.write(f"λ{i+1} = {ev:.4f}")
                    
                    st.write("#### 고유벡터:")
                    for i, evec in enumerate(eigenvecs.T):
                        st.write(f"v{i+1} = {evec}")
                    
                    # 특성 방정식 시각화
                    x = np.linspace(min(eigenvals.real)-2, max(eigenvals.real)+2, 1000)
                    coeffs = np.poly(A)
                    y = np.polyval(coeffs, x)
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=x, y=y, name='특성 방정식'))
                    fig.add_trace(go.Scatter(
                        x=eigenvals.real,
                        y=np.zeros_like(eigenvals.real),
                        mode='markers',
                        name='고유값',
                        marker=dict(size=10)
                    ))
                    fig.update_layout(title='특성 방정식과 고유값')
                    st.plotly_chart(fig)
                    
                except Exception as e:
                    st.error(f"계산 중 오류 발생: {str(e)}")
        
        elif analysis_type == "행렬 분해":
            st.write("### 행렬 분해")
            
            decomp_type = st.selectbox(
                "분해 방법",
                ["LU 분해", "QR 분해", "SVD 분해", "Cholesky 분해"]
            )
            
            matrix = st.text_area(
                "행렬 입력",
                "1 2 3\n4 5 6\n7 8 9",
                help="공백으로 구분된 행렬 입력"
            )
            
            A = parse_matrix_input(matrix)
            if A is not None:
                try:
                    if decomp_type == "LU 분해":
                        P, L, U = linalg.lu(A)
                        st.write("#### P (순열 행렬):")
                        st.write(P)
                        st.write("#### L (하삼각 행렬):")
                        st.write(L)
                        st.write("#### U (상삼각 행렬):")
                        st.write(U)
                        
                        # 시각화
                        fig = make_subplots(rows=1, cols=3, subplot_titles=('P', 'L', 'U'))
                        fig.add_trace(go.Heatmap(z=P, colorscale='RdBu'), row=1, col=1)
                        fig.add_trace(go.Heatmap(z=L, colorscale='RdBu'), row=1, col=2)
                        fig.add_trace(go.Heatmap(z=U, colorscale='RdBu'), row=1, col=3)
                        st.plotly_chart(fig)
                        
                    elif decomp_type == "QR 분해":
                        Q, R = np.linalg.qr(A)
                        st.write("#### Q (직교 행렬):")
                        st.write(Q)
                        st.write("#### R (상삼각 행렬):")
                        st.write(R)
                        
                        # 시각화
                        fig = make_subplots(rows=1, cols=2, subplot_titles=('Q', 'R'))
                        fig.add_trace(go.Heatmap(z=Q, colorscale='RdBu'), row=1, col=1)
                        fig.add_trace(go.Heatmap(z=R, colorscale='RdBu'), row=1, col=2)
                        st.plotly_chart(fig)
                        
                    elif decomp_type == "SVD 분해":
                        U, s, Vh = np.linalg.svd(A)
                        st.write("#### U (왼쪽 특이 벡터):")
                        st.write(U)
                        st.write("#### 특이값:")
                        st.write(s)
                        st.write("#### V^H (오른쪽 특이 벡터의 켤레 전치):")
                        st.write(Vh)
                        
                        # 특이값 시각화
                        fig = go.Figure()
                        fig.add_trace(go.Bar(
                            x=list(range(1, len(s)+1)),
                            y=s,
                            name='특이값'
                        ))
                        fig.update_layout(title='특이값 분포')
                        st.plotly_chart(fig)
                        
                    else:  # Cholesky 분해
                        try:
                            L = np.linalg.cholesky(A)
                            st.write("#### L (하삼각 행렬):")
                            st.write(L)
                            
                            # 시각화
                            fig = go.Figure(data=[go.Heatmap(z=L, colorscale='RdBu')])
                            fig.update_layout(title='Cholesky 분해 결과')
                            st.plotly_chart(fig)
                        except np.linalg.LinAlgError:
                            st.error("행렬이 양정치 대칭이 아닙니다.")
                            
                except Exception as e:
                    st.error(f"분해 중 오류 발생: {str(e)}")
        
        elif analysis_type == "선형 시스템":
            st.write("### 선형 시스템 Ax = b 풀이")
            
            col1, col2 = st.columns(2)
            
            with col1:
                matrix_a = st.text_area(
                    "계수 행렬 A 입력",
                    "1 2\n3 4",
                    help="공백으로 구분된 행렬 입력"
                )
            
            with col2:
                vector_b = st.text_area(
                    "상수 벡터 b 입력",
                    "5\n6",
                    help="한 줄에 하나의 값"
                )
            
            A = parse_matrix_input(matrix_a)
            b = parse_matrix_input(vector_b)
            
            if A is not None and b is not None:
                try:
                    x = np.linalg.solve(A, b)
                    st.write("#### 해:")
                    st.write(x)
                    
                    # 잔차 계산
                    residual = np.linalg.norm(A @ x - b)
                    st.write(f"잔차 (||Ax - b||): {residual:.2e}")
                    
                    # 2D 또는 3D 시각화
                    if A.shape[1] == 2:  # 2D 케이스
                        x_range = np.linspace(min(x[0]-2, 0), max(x[0]+2, 0), 100)
                        y_range = np.linspace(min(x[1]-2, 0), max(x[1]+2, 0), 100)
                        X, Y = np.meshgrid(x_range, y_range)
                        
                        Z1 = A[0,0]*X + A[0,1]*Y - b[0]
                        Z2 = A[1,0]*X + A[1,1]*Y - b[1]
                        
                        fig = go.Figure()
                        fig.add_trace(go.Contour(x=x_range, y=y_range, z=Z1, name='방정식 1'))
                        fig.add_trace(go.Contour(x=x_range, y=y_range, z=Z2, name='방정식 2'))
                        fig.add_trace(go.Scatter(
                            x=[x[0]], y=[x[1]],
                            mode='markers',
                            name='해',
                            marker=dict(size=10)
                        ))
                        fig.update_layout(title='선형 시스템의 해')
                        st.plotly_chart(fig)
                        
                except Exception as e:
                    st.error(f"계산 중 오류 발생: {str(e)}")
        
        elif analysis_type == "벡터 공간":
            st.write("### 벡터 공간 분석")
            
            matrix = st.text_area(
                "행렬 입력",
                "1 2 3\n4 5 6\n7 8 9",
                help="공백으로 구분된 행렬 입력"
            )
            
            A = parse_matrix_input(matrix)
            if A is not None:
                try:
                    # 계수(rank) 계산
                    rank = np.linalg.matrix_rank(A)
                    st.write(f"#### 행렬의 계수(rank): {rank}")
                    
                    # Null 공간 계산
                    U, s, Vh = np.linalg.svd(A)
                    null_space = Vh[rank:].T
                    if null_space.size > 0:
                        st.write("#### Null 공간의 기저:")
                        st.write(null_space)
                    else:
                        st.write("Null 공간은 {0} 뿐입니다.")
                    
                    # 조건수 계산
                    cond = np.linalg.cond(A)
                    st.write(f"#### 조건수: {cond:.2e}")
                    
                    # 행렬식 계산
                    if A.shape[0] == A.shape[1]:
                        det = np.linalg.det(A)
                        st.write(f"#### 행렬식: {det:.4f}")
                    
                    # 특이값 분해 기반 시각화
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=list(range(1, len(s)+1)),
                        y=s,
                        name='특이값'
                    ))
                    fig.update_layout(title='특이값 스펙트럼')
                    st.plotly_chart(fig)
                    
                except Exception as e:
                    st.error(f"계산 중 오류 발생: {str(e)}")

    # MATLAB/Octave 탭
    with tab5:
        st.subheader("MATLAB/Octave 코드 실행")
        
        # 실행 모드 선택
        mode = st.radio(
            "실행 모드",
            ["Python 변환", "Octave 직접 실행"],
            help="Python 변환: MATLAB/Octave 코드를 Python으로 변환하여 실행\nOctave 직접 실행: 시스템에 설치된 Octave로 직접 실행"
        )
        
        # 예제 코드 선택 (MATLAB/Octave 문법)
        example_codes = {
            "행렬 연산": """
A = [1 2 3; 4 5 6; 7 8 9];
B = [9 8 7; 6 5 4; 3 2 1];
C = A * B;
disp('결과 행렬:');
disp(C);
            """,
            "그래프 플로팅": """
x = linspace(-2*pi, 2*pi, 100);
y = sin(x);
plot(x, y);
xlabel('x');
ylabel('sin(x)');
title('Sine Wave');
            """,
            "3D 표면": """
[X,Y] = meshgrid(-5:0.1:5, -5:0.1:5);
Z = sin(sqrt(X.^2 + Y.^2));
mesh(X,Y,Z);
title('3D Surface Plot');
            """
        }
        
        example = st.selectbox(
            "예제 코드",
            ["직접 입력"] + list(example_codes.keys())
        )
        
        if example == "직접 입력":
            code = st.text_area(
                "MATLAB/Octave 코드 입력",
                "% 여기에 코드를 입력하세요\n",
                height=200
            )
        else:
            code = st.text_area(
                "코드",
                example_codes[example],
                height=200
            )
        
        if st.button("실행"):
            with st.spinner("코드 실행 중..."):
                if mode == "Octave 직접 실행":
                    output, error = run_octave_script(code)
                    if error:
                        st.error(error)
                    elif output:
                        st.code(output)
                else:  # Python 변환 모드
                    try:
                        # MATLAB 코드를 Python 코드로 변환
                        python_code = convert_matlab_to_python(code)
                        
                        # 실행 환경 설정
                        local_dict = {
                            'np': np,
                            'st': st,
                            'px': px,
                            'go': go,
                            'plot': lambda x, y: px.line(x=x, y=y),
                            'mesh': lambda X, Y, Z: go.Figure(data=[go.Surface(z=Z, x=X, y=Y)])
                        }
                        
                        # 코드 실행
                        exec(python_code, local_dict)
                    except Exception as e:
                        st.error(f"Python 변환 실행 중 오류 발생: {str(e)}")
        
        # 도움말 업데이트
        with st.expander("MATLAB/Octave 사용 도움말"):
            st.markdown("""
            ### 기본 문법
            - 행렬 정의: `A = [1 2 3; 4 5 6]`
            - 행렬 연산: `*` (행렬곱), `+` (덧셈), `'` (전치)
            - 요소별 연산: `.*` (곱셈), `./` (나눗셈), `.^` (거듭제곱)
            
            ### 주요 함수
            - `linspace(start, end, n)`: 균일한 간격의 벡터 생성
            - `plot(x, y)`: 2D 그래프 그리기
            - `mesh(X, Y, Z)`: 3D 표면 그리기
            - `zeros(), ones(), eye()`: 특수 행렬 생성
            
            ### 주의사항
            - Octave 모드는 시스템에 Octave가 설치되어 있어야 합니다
            - Python 변환 모드는 일부 MATLAB/Octave 함수만 지원합니다
            - 그래프는 자동으로 표시됩니다
            """)

if __name__ == "__main__":
    main() 