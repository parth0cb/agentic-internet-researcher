
const queryInput = document.getElementById('query');
const searchTypeSelect = document.getElementById('searchType');
const searchBtn = document.getElementById('searchBtn');
const resultsDiv = document.getElementById('results');
const tokenInfoDiv = document.getElementById('tokenInfo');
const stepsSection = document.getElementById('steps-section')
const stepsList = document.getElementById('steps-list')
const showStepsButton = document.getElementById('show-steps-button')
const hideStepsButton = document.getElementById('hide-steps-button')
const explanationDiv = document.getElementById('explanation')

let currentRequest = null;

searchBtn.addEventListener('click', async () => {

    const query = queryInput.value.trim();
    const selectedSearchType = searchTypeSelect.value;
    
    if (!query) {
        resultsDiv.innerHTML = '<div class="error">Please enter a search query.</div>';
        return;
    }

    if (selectedSearchType === 'none') {
        resultsDiv.innerHTML = '<div class="error">Select Search Type.</div>';

        return;
    }

    searchBtn.disabled = true;
    
    // Clear previous results
    resultsDiv.innerHTML = '';
    tokenInfoDiv.textContent = 'Input Tokens: 0 | Output Tokens: 0';
    

    // Cancel previous request if any
    if (currentRequest) {
        currentRequest.abort();
    }
    
    // Create new AbortController
    const controller = new AbortController();
    currentRequest = controller;

    // showSteps();

    resultsDiv.style.display = 'none'
    explanationDiv.style.display = 'block'
    explanationDiv.innerHTML = `<div class="loading-container"><div class="spinner"></div><div class="log">Loading...</div></div>`

    stepsList.innerHTML = ''
    
    try {
        const response = await fetch(`/search/${selectedSearchType}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query }),
            signal: controller.signal
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        let accumulatedData = '';
        let inputTokens = 0;
        let outputTokens = 0;
        
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) break;
            
            const chunk = decoder.decode(value, { stream: true });
            accumulatedData += chunk;
            
            // Process each line (JSON object)
            const lines = accumulatedData.split('\n');
            accumulatedData = lines.pop(); // Keep last incomplete line
            
            for (const line of lines) {
                if (!line.trim()) continue;
                
                try {
                    const data = JSON.parse(line);
                    
                    if (data.type === 'output') {
                        resultsDiv.style.display = 'block'
                        resultsDiv.innerHTML = data.content;
                        explanationDiv.innerHTML = ""
                        explanationDiv.style.display = 'none'
                    } else if (data.type === 'log') {
                        if (data.content.explanation) {
                            explanationDiv.innerHTML = `<div class="loading-container"><div class="spinner"></div><div class="log">${data.content.explanation}</div></div>`;
                            stepsList.innerHTML += `<li class="steps-list-element">Searched "${data.content.query}"</li>`
                        } else {
                            explanationDiv.innerHTML = `<div class="loading-container"><div class="spinner"></div><div class="log">${data.content}</div></div>`;
                        }

                    } else if (data.type === 'token_usage') {
                        inputTokens = data.content.prompt_tokens;
                        outputTokens = data.content.completion_tokens;
                        tokenInfoDiv.textContent = 
                            `Input Tokens: ${inputTokens} | Output Tokens: ${outputTokens}`;
                    } else if (data.type === 'error') {
                        resultsDiv.style.display = 'block'
                        resultsDiv.innerHTML = `<div class="error">Error: ${data.content}</div>`
                        explanationDiv.innerHTML = ""
                        explanationDiv.style.display = 'none'
                    }
                } catch (e) {
                    console.error('Error parsing JSON:', e);
                }
            }
        }
        
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('Request was aborted');
        } else {
            resultsDiv.innerHTML = `<div class="error">Error: ${error.message}</div>`;
        }
    } finally {
        currentRequest = null;
        searchBtn.disabled = false;
        const resultLinks = document.querySelectorAll('.results a');
        resultLinks.forEach(link => {
            link.classList.add('result_link')
            link.setAttribute('target', '_blank');
            link.setAttribute('rel', 'noopener noreferrer');
        hideSteps();
        });
    }
});

// Allow Enter key to trigger search
queryInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        searchBtn.click();
    }
});

function showSteps() {
    showStepsButton.style.display = 'none'
    hideStepsButton.style.display = 'block'
    stepsSection.style.display = 'block'
}

function hideSteps() {
    showStepsButton.style.display = 'block'
    hideStepsButton.style.display = 'none'
    stepsSection.style.display = 'none'
}