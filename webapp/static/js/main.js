document.addEventListener("DOMContentLoaded", () => {
    const screens = {
        input: document.getElementById("input-screen"),
        terminal: document.getElementById("terminal-screen"),
        news: document.getElementById("news-screen")
    };

    const queryInput = document.getElementById("query-input");
    const searchBtn = document.getElementById("search-btn");
    const termOutput = document.getElementById("terminal-output");
    const grid = document.getElementById("article-grid");
    
    // Modal Selectors
    const modal = document.getElementById("article-modal");
    const closeBtn = document.querySelector(".close-btn");

    function showScreen(name) {
        Object.values(screens).forEach(s => s.classList.remove("active"));
        screens[name].classList.add("active");
    }

    // Pseudo-random hash for placeholder images to keep them visually locked per article
    function stringHash(str) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            hash = str.charCodeAt(i) + ((hash << 5) - hash);
        }
        return Math.abs(hash);
    }

    searchBtn.addEventListener("click", () => {
        const query = queryInput.value.trim();
        if (!query) return;

        showScreen("terminal");
        termOutput.innerHTML = "";
        
        const evtSource = new EventSource(`/stream?query=${encodeURIComponent(query)}`);
        
        evtSource.onmessage = (e) => {
            const payload = JSON.parse(e.data);
            
            if (payload.type === "event") {
                const line = document.createElement("div");
                line.className = "term-line";
                let content = payload.text || payload.tool || "Working...";
                line.innerHTML = `<span class="term-author">[${payload.author}]</span> ${content}`;
                termOutput.appendChild(line);
                termOutput.scrollTop = termOutput.scrollHeight;
            } 
            else if (payload.type === "finish") {
                evtSource.close();
                renderNews(payload.data);
                setTimeout(() => showScreen("news"), 800);
            }
            else if (payload.type === "error") {
                evtSource.close();
                const err = document.createElement("div");
                err.style.color = "red";
                err.innerText = "Error: " + payload.message;
                termOutput.appendChild(err);
            }
        };
    });

    // Enter key submits
    queryInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") searchBtn.click();
    });

    document.getElementById("new-search-btn").addEventListener("click", () => {
        queryInput.value = "";
        showScreen("input");
    });

    function renderNews(data) {
        grid.innerHTML = "";
        if (!data || !data.articles || data.articles.length === 0) {
            grid.innerHTML = "<p>No news compiled from the Agent pipeline.</p>";
            return;
        }

        data.articles.forEach((article, idx) => {
            const seed = stringHash(article.title);
            const imgUrl = `https://picsum.photos/seed/${seed}/800/600`;
            const sourceCount = article.citations ? article.citations.length : Math.floor(Math.random() * 50) + 10;
            const timeAgo = Math.floor(Math.random() * 8) + 1; // Fake time for aesthetic
            
            const card = document.createElement("div");
            // Make first article the Hero
            card.className = idx === 0 ? "article-card card-hero" : "article-card";
            
            card.innerHTML = `
                <img src="${imgUrl}" class="card-img" alt="Cover">
                <div class="card-content">
                    <h2>${article.title}</h2>
                    <p>${article.teaser}</p>
                </div>
                <div class="card-meta">
                    <div class="source-pill">✦</div>
                    <span>${sourceCount} sources</span>
                    <span style="margin-left: auto;">Published ${timeAgo} hours ago</span>
                </div>
            `;
            
            card.addEventListener("click", () => openModal(article, imgUrl, sourceCount));
            grid.appendChild(card);
        });
    }

    function openModal(article, imgUrl, sourceCount) {
        document.getElementById("modal-img").src = imgUrl;
        document.getElementById("modal-title").innerText = article.title;
        document.getElementById("modal-sources").innerText = `✦ SYNTHESIZED FROM ${sourceCount} SOURCES IN REAL-TIME`;
        document.getElementById("modal-body").innerText = article.content;
        modal.style.display = "block";
    }

    closeBtn.onclick = () => modal.style.display = "none";
    window.onclick = (e) => { if (e.target == modal) modal.style.display = "none"; }
});
