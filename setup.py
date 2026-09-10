from setuptools import setup, find_packages

setup(
    name="hiver-support-agent",
    version="0.1.0",
    description="AI-powered customer support agent for Twitter conversations",
    author="SDE Intern",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "python-dotenv>=1.0.0",
        "pydantic>=2.5.0",
        "requests>=2.31.0",
        "openai>=1.7.2",
        "pandas>=2.1.3",
        "numpy>=1.26.2",
        "transformers>=4.35.2",
        "scikit-learn>=1.3.2",
        "pytest>=7.4.3",
        "tqdm>=4.66.1",
    ],
)
