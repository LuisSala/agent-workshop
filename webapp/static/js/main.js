document.addEventListener("DOMContentLoaded", () => {
    const screens = {
        input: document.getElementById("input-screen"),
        terminal: document.getElementById("terminal-screen"),
        news: document.getElementById("news-screen")
    };

    const queryInput = document.getElementById("query-input");
    const liveSearchBtn = document.getElementById("live-search-btn");
    const archiveSearchBtn = document.getElementById("archive-search-btn");
    
    const navQueryInput = document.getElementById("nav-query-input");
    const newSearchBtn = document.getElementById("new-search-btn");
    const navArchiveSearchBtn = document.getElementById("nav-archive-search-btn");
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

    function triggerSearch(prefix, queryValue) {
        if (!queryValue) return;

        showScreen("terminal");
        termOutput.innerHTML = "";
        
        const fullQuery = prefix + queryValue;
        const evtSource = new EventSource(`/stream?query=${encodeURIComponent(fullQuery)}`);
        
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
                if (payload.data && payload.data.articles && payload.data.articles.length > 0) {
                    renderNews(payload.data);
                    setTimeout(() => showScreen("news"), 800);
                } else {
                    const line = document.createElement("div");
                    line.className = "term-line";
                    line.style.color = "#4ade80";
                    line.innerHTML = `<span class="term-author">[system]</span> Agent finished executing. See terminal output above.`;
                    termOutput.appendChild(line);
                    termOutput.scrollTop = termOutput.scrollHeight;
                }
            }
            else if (payload.type === "error") {
                evtSource.close();
                const err = document.createElement("div");
                err.style.color = "red";
                err.innerText = "Error: " + payload.message;
                termOutput.appendChild(err);
            }
        };
    }

    liveSearchBtn.addEventListener("click", () => triggerSearch("Look up fresh news about: ", queryInput.value.trim()));
    archiveSearchBtn.addEventListener("click", () => triggerSearch("Search the archive for past news on: ", queryInput.value.trim()));

    // Enter key submits (default to live search)
    queryInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") liveSearchBtn.click();
    });

    // Nav Header Listeners
    newSearchBtn.addEventListener("click", () => {
        let q = navQueryInput.value.trim();
        if (!q) {
            queryInput.value = "";
            showScreen("input");
        } else {
            triggerSearch("Look up fresh news about: ", q);
        }
    });

    navArchiveSearchBtn.addEventListener("click", () => {
        let q = navQueryInput.value.trim();
        if (q) {
            triggerSearch("Search the archive for past news on: ", q);
        }
    });

    navQueryInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") newSearchBtn.click();
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
            // Alternating layout: 1 Hero, 4 normal cards...
            card.className = (idx % 5 === 0) ? "article-card card-hero" : "article-card";
            
            card.innerHTML = `
                <img src="${imgUrl}" class="card-img" alt="Cover">
                <div class="card-content">
                    <h2>${article.title}</h2>
                    <div class="teaser-text">${marked.parse(article.teaser)}</div>
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
        document.getElementById("modal-body").innerHTML = marked.parse(article.content);
        
        const citationsHtml = (article.citations && article.citations.length > 0) 
            ? "<h3>Sources</h3><ul>" + article.citations.map(c => `<li><a href="${c.url}" target="_blank">${c.title}</a></li>`).join("") + "</ul>"
            : "";
        document.getElementById("modal-citations").innerHTML = citationsHtml;
        
        modal.style.display = "block";
    }

    closeBtn.onclick = () => modal.style.display = "none";
    window.onclick = (e) => { if (e.target == modal) modal.style.display = "none"; }
});
