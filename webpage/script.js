const SUBLINK_URL = "https://raw.githubusercontent.com/aghrabooti/V2ray_crawler/refs/heads/main/crawler/sublink.txt";

let configs = [];
let map = null;
let markers = [];


// ============================================================
// GET COUNTRY FROM FLAG
// ============================================================

function getCountryCode(config) {

    const match = config.match(
        /#(.*)$/
    );

    if (!match) {
        return null;
    }

    let name = decodeURIComponent(
        match[1]
    );

    const flagMatch = name.match(
        /([\u{1F1E6}-\u{1F1FF}]{2})/u
    );

    if (!flagMatch) {
        return null;
    }

    const flag = [...flagMatch[1]];

    if (flag.length !== 2) {
        return null;
    }

    const first =
        flag[0].codePointAt(0) - 127397;

    const second =
        flag[1].codePointAt(0) - 127397;

    return String.fromCharCode(
        first,
        second
    );
}


// ============================================================
// GET CONFIG TYPE
// ============================================================

function getConfigType(config) {

    const lower = config.toLowerCase();

    if (lower.startsWith("vless://")) {
        return "VLESS";
    }

    if (lower.startsWith("vmess://")) {
        return "VMess";
    }

    if (lower.startsWith("trojan://")) {
        return "Trojan";
    }

    if (lower.startsWith("ss://")) {
        return "Shadowsocks";
    }

    if (lower.startsWith("ssr://")) {
        return "ShadowsocksR";
    }

    return "Unknown";
}


// ============================================================
// LOAD SUBLINK
// ============================================================

async function loadConfigs() {

    const response = await fetch(
        SUBLINK_URL + "?t=" + Date.now()
    );

    if (!response.ok) {
        throw new Error(
            `Failed to load sublink: ${response.status}`
        );
    }

    const text = await response.text();

    const lines = text
        .split(/\r?\n/)
        .map(line => line.trim())
        .filter(line => line.length > 0);

    configs = lines
        .map((line, index) => {

            const countryCode =
                getCountryCode(line);

            const country =
                countryCode
                    ? countries[countryCode]
                    : null;

            return {

                id: index + 1,

                raw: line,

                countryCode,

                country,

                type: getConfigType(line)

            };

        })
        .filter(config =>
            config.country !== null
        );

    populateCountrySelect();

    renderConfigs();

    initMap();

}


// ============================================================
// COUNTRY SELECT
// ============================================================

function populateCountrySelect() {

    const select =
        document.getElementById(
            "countrySelect"
        );

    select.innerHTML = "";

    const allOption =
        document.createElement("option");

    allOption.value = "ALL";
    allOption.textContent =
        "All Countries";

    select.appendChild(
        allOption
    );


    const countryCodes =
        [
            ...new Set(
                configs
                    .map(config =>
                        config.countryCode
                    )
                    .filter(Boolean)
            )
        ];


    countryCodes.sort(
        (a, b) =>
            countries[a].name.localeCompare(
                countries[b].name
            )
    );


    countryCodes.forEach(code => {

        const country =
            countries[code];

        const option =
            document.createElement(
                "option"
            );

        option.value = code;

        option.textContent =
            `${country.flag} ${country.name}`;

        select.appendChild(
            option
        );

    });


    select.addEventListener(
        "change",
        renderConfigs
    );

}


// ============================================================
// RENDER CONFIGS
// ============================================================

function renderConfigs() {

    const list =
        document.getElementById(
            "configList"
        );

    const selectedCountry =
        document.getElementById(
            "countrySelect"
        ).value;


    let filtered =
        configs;


    if (selectedCountry !== "ALL") {

        filtered =
            configs.filter(
                config =>
                    config.countryCode ===
                    selectedCountry
            );

    }


    list.innerHTML = "";


    if (filtered.length === 0) {

        list.innerHTML = `

            <div
                class="
                    rounded-2xl
                    border
                    border-white/[0.06]
                    bg-[#101217]
                    p-8
                    text-center
                "
            >

                <p class="text-gray-500 text-sm">
                    No configurations found.
                </p>

            </div>

        `;

        return;

    }


    filtered.forEach(
        (config, index) => {

            const card =
                document.createElement(
                    "div"
                );

            card.className = `
                config-card
                bg-[#101217]
                border
                border-[#1d2028]
                rounded-2xl
                p-5
                md:p-6
            `;


            card.innerHTML = `

                <div
                    class="
                        flex
                        flex-col
                        sm:flex-row
                        sm:items-center
                        justify-between
                        gap-5
                    "
                >

                    <div
                        class="
                            flex
                            items-center
                            gap-4
                        "
                    >

                        <div
                            class="
                                w-14
                                h-14
                                rounded-xl
                                bg-white/[0.04]
                                border
                                border-white/[0.06]
                                flex
                                items-center
                                justify-center
                                overflow-hidden
                            "
                        >
                            <img
                                src="https://flagcdn.com/w80/${config.countryCode.toLowerCase()}.png"
                                alt="${config.country.name}"
                                class="w-9 h-auto object-contain"
                            >
                        </div>


                        <div>

                            <div
                                class="
                                    flex
                                    items-center
                                    gap-2
                                "
                            >

                                <h3
                                    class="
                                        font-semibold
                                        text-lg
                                    "
                                >
                                    ${config.country.name}
                                </h3>


                                <span
                                    class="
                                        text-[10px]
                                        px-2
                                        py-1
                                        rounded-md
                                        bg-violet-500/10
                                        text-violet-300
                                        border
                                        border-violet-500/10
                                    "
                                >
                                    ${config.type}
                                </span>

                            </div>


                            <p
                                class="
                                    text-xs
                                    text-gray-600
                                    mt-1
                                "
                            >
                                Config #${String(
                                    config.id
                                ).padStart(3, "0")}
                            </p>

                        </div>

                    </div>


                    <button
                        class="
                            copy-btn
                            w-full
                            sm:w-auto
                            px-6
                            py-3
                            rounded-xl
                            bg-violet-600
                            hover:bg-violet-500
                            text-sm
                            font-semibold
                            shadow-[0_8px_30px_rgba(124,58,237,0.18)]
                        "
                    >
                        Copy
                    </button>

                </div>

            `;


            const button =
                card.querySelector(
                    "button"
                );


            button.addEventListener(
                "click",
                async () => {

                    try {

                        await navigator.clipboard.writeText(
                            config.raw
                        );

                        const oldText =
                            button.textContent;

                        button.textContent =
                            "Copied!";

                        button.classList.remove(
                            "bg-violet-600"
                        );

                        button.classList.add(
                            "bg-green-600"
                        );


                        setTimeout(() => {

                            button.textContent =
                                oldText;

                            button.classList.remove(
                                "bg-green-600"
                            );

                            button.classList.add(
                                "bg-violet-600"
                            );

                        }, 1200);

                    } catch (error) {

                        console.error(
                            "Copy failed:",
                            error
                        );

                    }

                }
            );


            list.appendChild(card);

        }
    );

}


// ============================================================
// MAP
// ============================================================

function initMap() {

    if (map) {

        map.remove();

        markers = [];

    }


    map = L.map(
        "worldMap",
        {
            zoomControl: true,
            attributionControl: false,
            minZoom: 2,
            maxZoom: 6
        }
    ).setView(
        [25, 10],
        2
    );


    L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        {
            maxZoom: 6
        }
    ).addTo(map);


    const countryCounts = {};


    configs.forEach(config => {

        const code =
            config.countryCode;

        if (!code) {
            return;
        }

        countryCounts[code] =
            (countryCounts[code] || 0) + 1;

    });


    Object.entries(
        countryCounts
    ).forEach(
        ([code, count]) => {

            const country =
                countries[code];

            if (!country) {
                return;
            }


            const marker =
                L.circleMarker(
                    [
                        country.lat,
                        country.lng
                    ],
                    {

                        radius:
                            Math.min(
                                8 + count,
                                16
                            ),

                        fillColor:
                            "#22d3ee",

                        color:
                            "#67e8f9",

                        weight: 2,

                        opacity: 1,

                        fillOpacity: 0.85

                    }
                );


            marker.bindPopup(`

                <div>

                    <div
                        style="
                            font-size:15px;
                            font-weight:700;
                            margin-bottom:6px;
                        "
                    >
                        ${country.flag}
                        ${country.name}
                    </div>

                    <div
                        style="
                            font-size:13px;
                            color:#9ca3af;
                        "
                    >
                        ${count}
                        configuration${count !== 1 ? "s" : ""}
                    </div>

                </div>

            `);


            marker.addTo(map);

            markers.push(marker);

        }
    );

}


// ============================================================
// START
// ============================================================

loadConfigs().catch(error => {

    console.error(
        "CONFIG LOAD ERROR:",
        error
    );


    const list =
        document.getElementById(
            "configList"
        );


    list.innerHTML = `

        <div
            class="
                rounded-2xl
                border
                border-red-500/10
                bg-[#101217]
                p-8
                text-center
            "
        >

            <p class="text-red-400 text-sm">
                Failed to load configurations.
            </p>

            <p
                class="
                    text-gray-600
                    text-xs
                    mt-2
                "
            >
                ${error.message}
            </p>

        </div>

    `;

});

const SUBLINK_URL = "../crawler/sublink.txt";


        const copyAllButton =
            document.getElementById(
                "copyAllConfigs"
            );


        const copyAllText =
            document.getElementById(
                "copyAllText"
            );


        copyAllButton.addEventListener(
            "click",
            async () => {

                const originalText =
                    "Copy All Configs";


                try {

                    copyAllText.textContent =
                        "Loading...";


                    const response =
                        await fetch(
                            SUBLINK_URL,
                            {
                                cache: "no-store"
                            }
                        );


                    if (!response.ok) {

                        throw new Error(
                            `HTTP ${response.status}`
                        );

                    }


                    const configs =
                        await response.text();


                    if (!configs.trim()) {

                        throw new Error(
                            "No configurations found."
                        );

                    }


                    await navigator.clipboard.writeText(
                        configs
                    );


                    copyAllText.textContent =
                        "✓ Copied!";


                    setTimeout(
                        () => {

                            copyAllText.textContent =
                                originalText;

                        },
                        2000
                    );


                } catch (error) {

                    console.error(
                        "Failed to copy configs:",
                        error
                    );


                    /*
                     * Fallback for browsers where
                     * Clipboard API is unavailable.
                     */

                    try {

                        const textarea =
                            document.createElement(
                                "textarea"
                            );


                        textarea.value =
                            await fetch(
                                SUBLINK_URL,
                                {
                                    cache: "no-store"
                                }
                            ).then(
                                response =>
                                    response.text()
                            );


                        textarea.style.position =
                            "fixed";

                        textarea.style.opacity =
                            "0";


                        document.body.appendChild(
                            textarea
                        );


                        textarea.select();


                        document.execCommand(
                            "copy"
                        );


                        textarea.remove();


                        copyAllText.textContent =
                            "✓ Copied!";


                        setTimeout(
                            () => {

                                copyAllText.textContent =
                                    originalText;

                            },
                            2000
                        );


                    } catch (fallbackError) {

                        console.error(
                            "Copy failed:",
                            fallbackError
                        );


                        copyAllText.textContent =
                            "Copy failed";


                        setTimeout(
                            () => {

                                copyAllText.textContent =
                                    originalText;

                            },
                            2000
                        );

                    }

                }

            }
        );