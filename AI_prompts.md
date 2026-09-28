# AI Prompts Log

## Setup (before Problem 1)

### Prompts typed

> I want to work in my hw 4 folder today, make sure we are there

> write me a joke there to show you are there

> I want to give you context for what I want to do, nothing you have to do just yet. I want to create a real customer website with a helpful chatbot. I will build a React + Vite TypeScript front end and python fastapi backend whose brain is pydanticAI agent. Shoppers will be able to browse products, create an account, chat about merch, see matching items appear on the page, and get honest ansers about price and stock form a local database. I am given campus_customs.db with tables for product catalogue, inventory by size, and users (with hashed passwords). product image file paths are in the catalogue table. Research yalebulldogblue.com to learn style of Campus Customs page and information for the agent prompt. Use my PORTKEY_API_Key , and when using openAI through portkey use models in the 5.6 or 6 series. I will type each problem and in the end I will push the project to a public GitHUB repo. I do not want to commit the database or product images. Does that make sense? again, no need to do anything just yet

## Problem 1: Vibe Coder Prompts

### Prompt typed

> Problem 1: Vibe Coder Prompts. Create AI_prompts.md to keep updated as I work, this is the file of log of what I type into this vibe coder. Put one section for each problem, and each section to include the prbolem number and title, at least one prompt I typed, and a follow up prompt as needed with a sentence on what was lacking from the first.

### Follow-up prompt

None yet. The initial prompt specified the file name, the one-section-per-problem structure, and the required contents of each section.

## Problem 2: Analyze the Database

### Prompt typed

> Problem 2: Analyze the Database. Look at the database data/campus_customs.db and understand the fields of each table. Minimally you should understand catalogue, inventory, and users. Start the file output/harness.md and write down each table and its fields, and one short line on why each field matters for the shop or the chatbot. Grow this harness file in later problems for models, tools, safety, specs, etc.

### Follow-up prompt

None yet. The initial prompt named the database, the minimum tables, the output file, and the per-field format.

## Problem 3: Research the Campus Customs site

### Prompt typed

> Problem 3: Research the Campus Customs site. Scaffold a react + vite + typescript front end for Campus Customs. Put a nav bar at the top that links to the main pages: Home, Products, About Us, Log In, Create Account. Pull campus customs-style wording from the site yalebulldogblue.com for Home and About us, but write these pages in your own voice and DO NOT COPY ORIGINAL SITE TEXT.  On Products page, I want to show the produc timages from the catalogue, using the image paths in the database with basic product info such as name, pricing, and a short description. Make each product open a single-item page (large image on one side, full product text on the other, description, price, sizes/stocks when you ahve them). Clicking a card on products should take the shopper there. I want a chat interface at the bottom right of the site such as a floating chat panel. Does not have to talk to agent yet, a stub that will backend later is fine enough for now. Start a simple FastAPI app in backend/main.py just to serve products and images, then grow it into the agent backend later down the line when I do problem 5.

### Follow-up prompt

None yet. The initial prompt did not say whether to follow the site's navy-and-white colors or the project's black-and-pink rule, so black and pink was used with the Campus Customs layout and tone.

## Problem 4: Create Account and Login

### Prompt typed

> Problem 4: Create Account and Login. Build a normal create account login flow through 1) Create Account (first name, last name, email, password, confirm password) 2) Log in (email and password). New accounts should go into the users table and make sure to store passwords securely so human or AI hackers cannot access. Seed database has a test user you can use while building: email: test@campuscustoms.yale.edu, password: password. Confirm you can log in as that user and that a brand new account created also works. Update output/harness.md with how authentication should work (what you store for a user and how passwords are protected).

### Follow-up prompt

None yet. The initial prompt did not specify how logged-in sessions should be kept or what should happen after repeated wrong passwords, so HttpOnly cookie sessions and a 5-attempt lockout were added.

## Problem 5: Shop Chatbot Agent

### Prompt typed

> Problem 5: Build the shop chatbot as pydanticAI agent behind FastAPI, plugged into the front end chat widget. Put the api app in backend/main.py (this is the file you run with Uvicorn). Keep agent as these four files next to it, similar to what we did in hw 3: backend/prompts/prompt.md - system prompt (grow this file later). backend/agent.py - agent entry/wiring. backend/tools.py - tools the agent can call. backend/models.py - pydantic / pydanticAI structured types. In main.py, expose a chat route so message from website returns a reply from the agent. use my AI model API key for the agent. Put campus customs voice and safety basics into prompts/prompt.md (we will expand tools and safety later). Start or update types in models.py for chat replies and product cards as needed. In output/harness.md, note how the front end talks to FastAPI and how the agent is loaded (prompt file + model). make sure the backend runs from backend/folder like so: uvicorn main:app --reload --port 8000

### Follow-up prompt

None yet. The initial prompt did not say how follow-up questions should remember which products were shown, so product ids are now sent with chat history after a test where "the first one" was misread.

## Problem 6: Tools: Product Info and Stock

### Prompt typed

> Problem 6: now give the agent tools to look up information from campus_customs.db: product description, price, how many are in stock(by size when customer asks). The agent should use the database, DO NOT invent prices or quantities, if a size Is out of stock, say so clearly so make sure to double check pls. Expand prompts/prompt.md so the agent knows to call those tools for price and stock questions, and add or update return types in models.py. In output/harness.md, list each tool and explain which model fields you chose for lookup results and why.

### Follow-up prompt

> Problem 6 Tools: Product Info and Stock. now give the agent tools to look up information from campus_customs.db: product description, price, how many are in stock(by size when customer asks). The agent should use the database, DO NOT invent prices or quantities, if a size Is out of stock, say so clearly so make sure to double check pls. Expand prompts/prompt.md so the agent knows to call those tools for price and stock questions, and add or update return types in models.py. In output/harness.md, list each tool and explain which model fields you chose for lookup results and why.

The first prompt was missing the problem title ("Tools: Product Info and Stock"), so it was interrupted and re-sent with the full problem number and title.

## Problem 7: Chat Search that Updates the Page

### Prompt typed

> Problem 7: Chat Search that Updates the Page. When a customer asks about a type of item, e.g., what hoodies do you have, the agent should search catalogue and website should dynamically sohw matching items as product cards (image, name, price, short info). this is api contract, the agent returning structured product matches and then front end renders them on the website. after dynamic product cards loaded by this feature, make sure same single-item page behavior built in problem 3 earlier still works, as each product card, including the ones the chat put on page, should open the detail view (with large image and full info) when clicked. Update prompts/prompt.md and output/harness.md so it is clear how search results reach the page.

### Follow-up prompt

None yet. The initial prompt did not say where on the site the chat's cards should appear or how many to show, so they go in a "From your chat" grid at the top of the current page (up to 12, with a "See all" link).

## Problem 8: Customer Memory

### Prompt typed

> Problem 8: Customer Memory. When shopper logs in, save their chat history in database in an appropriate table and reload it when they return. Agent should know who is chatting (name and email), put that in agent deps (or equivalent clear pattern), and/or tools agent can call. Pass enough page context that if someone is on product page and asks do you have this in pink, agent knows which item they mean. Feel free to put code into the agent context. Guests can still chat, but history only needs to show for logged in users. Document in output/harness.md how user chat history is stored, what customer fields the agent sees, and how page context is passed.

### Follow-up prompt

None yet. The initial prompt did not say whether shoppers should be able to delete their saved chat or whether saved product cards should keep old prices, so a Clear button was added and cards are rebuilt from live prices when history reloads.

## Problem 9: Usability Improvements

### Prompt typed

> Problem 9: Usability Improvements. I want to implement 2 agent/backend usability improvements. Help me make the agent output better, more accurate, and safer. These could be new agent tools or things to help agent run faster and cheaper. Write output/usability.md before or as you build. Each improvements should say what you added and why it helps campus customs shopper or business. Make sure all improvements show up in the running app, double check as needed please.

### Follow-up prompt

None yet. The initial prompt left the choice of improvements open, so two were picked that each show up in the app: live progress while the agent works (streaming), and restock alerts for sold-out sizes (new agent tools).

## Problem 10: Style The Website

### Prompt typed

> Problem 10: Style The Website. I want to add creative design so site feels like real campus customs storefront. I am looking at the website right now and the coloring, fonts, hierarchy, motion, product presentation, and chat feel a little off. Help me do some research on the official Campus Customs storeftont at the link here: https://www.campuscustoms.com and imitate their website design. DO NOT purchase anything or contact their webiste please. we are just doing recon. Use a little psychology "warfare" such as when customers click purchase, there is flashy lights or a cool cliking sound on purchase to keep customers wanting to buy kind of like in a casino. I am open to suggestions from you too. Write output/design.md on what you changed and why it would help customers stick around and buy. Keep it concrete and short.

### Follow-up prompt

> (Answered a clarifying question) Color direction: "Match Campus Customs" — navy #0c233f + light blue #7ba0c5 on white, instead of the AGENTS.md black-and-pink rule.

The first prompt conflicted with the project's black-and-pink rule and didn't say which should win, so the color choice had to be confirmed. The site also had no purchase button yet, so a bag with a demo checkout was added to give the "purchase" celebration somewhere to happen.

## Problem 11: Site Testing (app check)

### Prompt typed

> Problem 11: Site Testing (app check). Test the live site and document in output/app_check.html, which should be a page I can double click to open. Include clear screenshots and short captions for 1. chat checking the inventory level of an item with honest stock and price from the database in my data folder. 2. dynamic search result cards appearing after a category question (e.g., hoodies). 3. one of the usability features added in Problem 9. Make sure the html page is easy to grade by such that the heading for each check, screenshot, one or two sentences on what screenshot proves. Put the screenshot image files in output/app_check_images/ and link them from app_check.html with relative paths (e..g, app_check_images/inventory.png).

### Follow-up prompt

None yet. The initial prompt did not say how to show that the chat's numbers really come from the database, so each check also includes the matching database rows read directly from data/campus_customs.db.

## Problem 12: Audit Trail, Safety, Finish Harness

### Prompt typed

> Problem 12: Audit Trail, Safety, Finish Harness. Keep an append only output/audit_trail.json of agent loop activity (time, tool name, short args/results, stop reason). Do not wipe it between runs. Also help me come up with some safety rules to get the agent and put them into prompts/prompt.md. Finish output/harness.md so it is clear how the system works. Model fields in models.py and why you chose them, tools and abilities, safety rules, specs (loop limits, result caps, models, how to run front and back end).

### Follow-up prompt

None yet. The initial prompt did not say whether safety rules should only be written in the prompt or also enforced in code, so the key ones (card/SSN redaction, no leaking other emails) are enforced in code too and marked 🔒 in prompt.md.

## Problem 13: Push to GitHub and submit the URL

### Prompt typed

> Problem 13: Push to GitHub and submit the URL. Please help me redact the shopper messages. I want you to help me put my code into a folder on my desktop named hw4, push what we worked on to a public GitHub repository. Then, give me the repo URL. Do not put my real .env, campus_customs.db, or product images in the GitHub repo. Use .gitignore. Include .env.example with placeholders only. See screenshots for what I want my file layout to be.

### Follow-up prompt

None yet. The initial prompt did not name the GitHub repository, so it was created as `hw4-campus-customs`, and the agent helper code was folded into the four agent files to match the required layout.
