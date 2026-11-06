import { db } from '../db/db';

const WEATHER_CACHE_ID = 'dashboard-weather';
const OPEN_METEO = 'https://api.open-meteo.com/v1/forecast';
const AIR_QUALITY = 'https://air-quality-api.open-meteo.com/v1/air-quality';

function getCentroid(plot) {
    const points = plot?.coordinates || plot?.boundaryCoordinates || [];
    const valid = points
        .map((point) => Array.isArray(point) ? point.map(Number) : [Number(point.latitude), Number(point.longitude)])
        .filter(([lat, lng]) => Number.isFinite(lat) && Number.isFinite(lng));
    if (!valid.length) return null;
    return [
        valid.reduce((sum, [lat]) => sum + lat, 0) / valid.length,
        valid.reduce((sum, [, lng]) => sum + lng, 0) / valid.length,
    ];
}

function conditionFromCode(code) {
    if ([0, 1].includes(code)) return 'weather.clear';
    if ([2, 3, 45, 48].includes(code)) return 'weather.cloudy';
    if ([51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82].includes(code)) return 'weather.rain';
    if ([71, 73, 75, 77, 85, 86].includes(code)) return 'weather.snow';
    if ([95, 96, 99].includes(code)) return 'weather.storm';
    return 'weather.unknown';
}

function buildAdvisories(data) {
    const rainNext3h = (data.hourly?.rain || []).slice(0, 3).reduce((sum, value) => sum + value, 0);
    const wind = data.current?.wind_speed_10m || 0;
    const humidity = data.current?.relative_humidity_2m || 0;
    const soilMoisture = data.current?.soil_moisture_0_to_1cm;
    const params = {
        wind: Math.round(wind),
        rainMm: Number(rainNext3h.toFixed(1)),
        humidity: Math.round(humidity),
    };
    return [
        { key: wind < 15 && rainNext3h < 0.5 && humidity < 85 ? 'weather.adviceSpray' : 'weather.adviceAvoidSpray', params, severity: wind < 15 && rainNext3h < 0.5 ? 'good' : 'warning' },
        { key: soilMoisture != null && soilMoisture < 0.25 && rainNext3h < 2 ? 'weather.adviceIrrigate' : 'weather.adviceIrrigationWait', params, severity: 'info' },
        { key: rainNext3h > 10 ? 'weather.adviceHeavyRain' : 'weather.adviceSowing', params, severity: rainNext3h > 10 ? 'warning' : 'good' },
    ];
}

export function buildSampleWeather(plot) {
    const [latitude, longitude] = getCentroid(plot) || [15.49, 73.82];
    const now = new Date();
    now.setMinutes(0, 0, 0);
    const startHour = new Date(now.getTime() - 2 * 3600 * 1000);
    const times = [];
    const temperature_2m = [];
    const apparent_temperature = [];
    const relative_humidity_2m = [];
    const precipitation_probability = [];
    const precipitation = [];
    const rain = [];
    const wind_speed_10m = [];
    const soil_moisture_0_to_1cm = [];

    for (let i = 0; i < 36; i += 1) {
        const dt = new Date(startHour.getTime() + i * 3600 * 1000);
        const hourOfDay = dt.getHours();
        times.push(dt.toISOString());
        const diurnal = Math.sin(((hourOfDay - 6) / 24) * Math.PI * 2);
        const temp = Number((28.5 + diurnal * 4.8).toFixed(1));
        const feels = Number((temp + 2.4 - diurnal * 0.4).toFixed(1));
        const hum = Math.round(Math.max(46, Math.min(92, 72 - diurnal * 18)));
        const rainProb = hourOfDay >= 15 && hourOfDay <= 19 ? 55 + ((hourOfDay - 15) * 8) : Math.max(8, 22 - Math.abs(hourOfDay - 16) * 2);
        const rainMm = rainProb >= 55 ? Number(((rainProb - 45) * 0.12).toFixed(1)) : 0;
        const wind = Number((9 + Math.max(0, diurnal) * 9.5).toFixed(1));
        const soilM = Number((0.28 + (rainMm > 0 ? 0.04 : 0) - Math.max(0, diurnal) * 0.03).toFixed(3));

        temperature_2m.push(temp);
        apparent_temperature.push(feels);
        relative_humidity_2m.push(hum);
        precipitation_probability.push(Math.min(95, Math.round(rainProb)));
        precipitation.push(rainMm);
        rain.push(rainMm);
        wind_speed_10m.push(wind);
        soil_moisture_0_to_1cm.push(soilM);
    }

    const dailyTime = [];
    const temperature_2m_min = [];
    const temperature_2m_max = [];
    const precipitation_sum = [];
    for (let d = 0; d < 7; d += 1) {
        const dayDate = new Date(now.getTime() + d * 86400 * 1000);
        dailyTime.push(dayDate.toISOString().slice(0, 10));
        temperature_2m_min.push(24 + (d % 2));
        temperature_2m_max.push(32 + ((d + 1) % 3));
        precipitation_sum.push(d === 2 || d === 4 ? 4.2 : 0.6);
    }

    const sample = {
        current: {
            temperature_2m: temperature_2m[2],
            apparent_temperature: apparent_temperature[2],
            relative_humidity_2m: relative_humidity_2m[2],
            wind_speed_10m: wind_speed_10m[2],
            pressure_msl: 1011,
            weather_code: 2,
            soil_moisture_0_to_1cm: soil_moisture_0_to_1cm[2],
        },
        hourly: {
            time: times,
            temperature_2m,
            apparent_temperature,
            relative_humidity_2m,
            precipitation_probability,
            precipitation,
            rain,
            wind_speed_10m,
            soil_moisture_0_to_1cm,
        },
        daily: {
            time: dailyTime,
            temperature_2m_min,
            temperature_2m_max,
            precipitation_sum,
        },
        air: { hourly: { us_aqi: [42] } },
        conditionKey: 'weather.cloudy',
        latitude,
        longitude,
        fetchedAt: new Date().toISOString(),
        isSample: true,
    };
    sample.advisories = buildAdvisories(sample);
    return sample;
}

export async function fetchWeather(plot) {
    let coordinates = getCentroid(plot);
    if (!coordinates && typeof navigator !== 'undefined' && navigator.geolocation) {
        coordinates = await new Promise((resolve) => navigator.geolocation.getCurrentPosition(
            ({ coords }) => resolve([coords.latitude, coords.longitude]),
            () => resolve([20, 0]),
            { timeout: 2500 },
        ));
    }
    const [latitude, longitude] = coordinates || [20, 0];
    const params = new URLSearchParams({
        latitude,
        longitude,
        timezone: 'auto',
        forecast_days: '10',
        current: 'temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,rain,weather_code,pressure_msl,cloud_cover,wind_speed_10m,wind_direction_10m,wind_gusts_10m,visibility,dew_point_2m,uv_index,soil_temperature_0cm,soil_temperature_6cm,soil_moisture_0_to_1cm,soil_moisture_3_to_9cm,et0_fao_evapotranspiration',
        hourly: 'temperature_2m,apparent_temperature,relative_humidity_2m,precipitation_probability,precipitation,rain,wind_speed_10m,wind_direction_10m,soil_temperature_0cm,soil_temperature_6cm,soil_moisture_0_to_1cm,soil_moisture_3_to_9cm,et0_fao_evapotranspiration',
        daily: 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,uv_index_max,sunrise,sunset',
    });
    const airParams = new URLSearchParams({ latitude, longitude, timezone: 'auto', hourly: 'us_aqi,pm2_5,pm10' });
    const [weatherResponse, airResponse] = await Promise.all([fetch(`${OPEN_METEO}?${params}`), fetch(`${AIR_QUALITY}?${airParams}`)]);
    if (!weatherResponse.ok) throw new Error('Weather service unavailable');
    const weather = await weatherResponse.json();
    const air = airResponse.ok ? await airResponse.json() : null;
    const normalized = { ...weather, air, conditionKey: conditionFromCode(weather.current?.weather_code), advisories: buildAdvisories(weather), latitude, longitude, fetchedAt: new Date().toISOString() };
    await db.weatherCache.put({ id: WEATHER_CACHE_ID, updatedAt: normalized.fetchedAt, data: normalized });
    return { data: normalized, stale: false };
}

export async function getCachedWeather() {
    const cached = await db.weatherCache.get(WEATHER_CACHE_ID);
    return cached ? { data: cached.data, stale: true, updatedAt: cached.updatedAt } : null;
}

export { conditionFromCode };
