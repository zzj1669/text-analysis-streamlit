import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import jieba
from collections import Counter
from pyecharts.charts import WordCloud, Bar, Line, Pie, Radar, Scatter, Funnel
from pyecharts import options as opts
from pyecharts.globals import ThemeType
from streamlit_echarts import st_pyecharts


# 停用词加载（过滤无意义词）
def load_stopwords():
    stopwords = set()
    try:
        with open("stopwords.txt", "r", encoding="utf-8") as f:
            for line in f:
                word = line.strip()
                if word:  # 跳过空行
                    stopwords.add(word)
    except FileNotFoundError:
        st.warning("未找到stopwords.txt，使用默认停用词")
        stopwords = {"的", "了", "在", "是", "和", "为", "等", "有", "也", "就", "都", "不", "而", "之"}
    except Exception as e:
        st.warning(f"读取停用词文件失败：{str(e)}，使用默认停用词")
        stopwords = {"的", "了", "在", "是", "和", "为", "等", "有", "也", "就"}
    return stopwords


stopwords = load_stopwords()


# 文本采集与清洗
def fetch_and_clean_text(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.body.get_text(separator="\n", strip=True)
        # 清洗HTML标签、标点
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    except Exception as e:
        st.error(f"URL采集失败：{str(e)}")
        return None


# 分词与词频统计（核心改动：强制过滤长度<2的词）
def get_word_counts(text, min_freq=1):
    # 第一步：分词后先过滤长度<2的词 + 过滤停用词
    words = [
        word for word in jieba.lcut(text)
        if len(word) >= 2  # 强制过滤所有单字（长度<2）
           and word not in stopwords  # 过滤停用词
    ]
    # 第二步：统计词频并过滤低频词
    word_counts = Counter(words).most_common()
    word_counts = [item for item in word_counts if item[1] >= min_freq]
    return word_counts[:20], word_counts  # 前20名 + 全部词频


# 绘制不同类型图表
def render_chart(chart_type, word_data):
    words, counts = zip(*word_data) if word_data else ([], [])
    if not words:
        st.warning("无有效词频数据（所有单字已过滤，且无符合条件的多字词）")
        return

    if chart_type == "词云":
        chart = (
            WordCloud(init_opts=opts.InitOpts(theme=ThemeType.LIGHT))
                .add("", list(zip(words, counts)), word_size_range=[20, 100])
                .set_global_opts(title_opts=opts.TitleOpts(title="词频词云"))
        )
    elif chart_type == "柱状图":
        chart = (
            Bar(init_opts=opts.InitOpts(theme=ThemeType.LIGHT))
                .add_xaxis(words)
                .add_yaxis("词频", counts)
                .reversal_axis()
                .set_global_opts(title_opts=opts.TitleOpts(title="词频柱状图"), xaxis_opts=opts.AxisOpts(name="词频"),
                                 yaxis_opts=opts.AxisOpts(name="词汇"))
        )
    elif chart_type == "折线图":
        chart = (
            Line(init_opts=opts.InitOpts(theme=ThemeType.LIGHT))
                .add_xaxis(words)
                .add_yaxis("词频", counts, markpoint_opts=opts.MarkPointOpts(data=[opts.MarkPointItem(type_="max")]))
                .set_global_opts(title_opts=opts.TitleOpts(title="词频折线图"))
        )
    elif chart_type == "饼图":
        chart = (
            Pie(init_opts=opts.InitOpts(theme=ThemeType.LIGHT))
                .add("", list(zip(words, counts)))
                .set_global_opts(title_opts=opts.TitleOpts(title="词频占比饼图"))
                .set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {c}"))
        )
    elif chart_type == "雷达图":
        chart = (
            Radar(init_opts=opts.InitOpts(theme=ThemeType.LIGHT))
                .add_schema(schema=[opts.RadarIndicatorItem(name=w, max_=max(counts)) for w in words[:6]])  # 取前6个词
                .add("词频", [counts[:6]])
                .set_global_opts(title_opts=opts.TitleOpts(title="词频雷达图"))
        )
    elif chart_type == "散点图":
        chart = (
            Scatter(init_opts=opts.InitOpts(theme=ThemeType.LIGHT))
                .add_xaxis(words)
                .add_yaxis("词频", counts)
                .set_global_opts(title_opts=opts.TitleOpts(title="词频散点图"),
                                 xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=-45)))
        )
    elif chart_type == "漏斗图":
        chart = (
            Funnel(init_opts=opts.InitOpts(theme=ThemeType.LIGHT))
                .add("词频", list(zip(words, counts)), sort_="descending")
                .set_global_opts(title_opts=opts.TitleOpts(title="词频漏斗图"))
        )
    st_pyecharts(chart, height=500)


# Streamlit应用主逻辑
def main():
    st.title("文本词频分析Web应用")

    # 1. 输入URL
    url = st.text_input("输入文章URL", placeholder="例如：https://www.example.com/article")

    if url:
        # 2. 采集并清洗文本
        text = fetch_and_clean_text(url)
        if text:
            st.success("文本采集成功！")
            st.expander("查看原始文本").write(text[:1000] + "..." if len(text) > 1000 else text)

            # 3. 交互式过滤低频词
            min_freq = st.slider("过滤词频低于以下的词汇", min_value=1, max_value=10, value=1)

            # 4. 分词统计（已强制过滤单字）
            top20_words, all_words = get_word_counts(text, min_freq)

            # 5. 侧边栏图表筛选
            st.sidebar.header("图表筛选")
            chart_types = ["词云", "柱状图", "折线图", "饼图", "雷达图", "散点图", "漏斗图"]
            selected_chart = st.sidebar.selectbox("选择图表类型", chart_types)

            # 6. 展示词频前20
            st.subheader("词频排名前20的词汇")
            st.table({"词汇": [w[0] for w in top20_words], "词频": [w[1] for w in top20_words]})

            # 7. 绘制选中的图表
            st.subheader(f"{selected_chart}展示")
            render_chart(selected_chart, top20_words)


if __name__ == "__main__":
    main()
