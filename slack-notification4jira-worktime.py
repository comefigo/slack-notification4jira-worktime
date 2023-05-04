#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
日別のJIRA作業実績を取得し、個人別にSlackに出力する
予実を見える化し、計画に対しての実績を意識することを目的とする
'''
from datetime import datetime, timedelta
from jira import JIRA
from slack_sdk import WebClient

# JIRAのログインユーザー
JIRA_EMAIL=""
# JIRA APIトークン
JIRA_API_TOKEN=""
# JIRAサーバーのURL
JIRA_SERVER=""
# JIRA プロジェクト
JIRA_PROJECT=""
JIRA_DATE_FORMAT="%Y-%m-%d"
# 作業実績の取得範囲（日）
JIRA_DAY=1
# Slack Bot Token
SLACK_BOT_TOKEN=""
# 通知先のSlackチャンネル名
SLACK_CHANNEL_NAME=""


class SlackBlockMsg:

    def __init__(self, username, tasks):
        self.type = "section"
        self.text = {}
        self.text["type"] = "mrkdwn"
        self.text["text"] = ""
        self.accessory = {}
        self.accessory["image_url"] = tasks["avatar"]
        self.accessory["alt_text"] = username
        self.accessory["type"] = "image"

        for id, task in tasks.items():
            if id not in ["total", "avatar"]:
                self.text["text"] += f"・<{JIRA_SERVER}/browse/{id}|{id}> {task['summary']} {task['timespent']}h（合）/{task['timeestimate']}h（見） {task['condition']}：　{task['spend_time']}h（本） \n"

def get_jira_issue_worklogs(start_of_today, end_of_today):
    jira = JIRA(server=JIRA_SERVER, basic_auth=(JIRA_EMAIL, JIRA_API_TOKEN))
    jira_pj = jira.project(JIRA_PROJECT)
    jql = f"project = {jira_pj.key} AND worklogDate >= {start_of_today.date()} AND worklogDate <= {end_of_today.date()}"
    issues = jira.search_issues(jql, maxResults=1000, expand="worklog")
    return issues

def slack_send_msg(channel_name, slack_msg_blocks):
    slack_client = WebClient(SLACK_BOT_TOKEN)
    slack_client.chat_postMessage(
        channel='#' + channel_name,
        text='hello',
        blocks=slack_msg_blocks
    )

# 予実に応じて絵文字を返す
# 予定時間と消費時間が同じ場合は、:greate_condition:を返す
# 予定時間より消費時間が多い場合は、:bad_condition:を返す
def get_condition_icon(timespent:int, timeestimate:int):
    icon = ":good_condition:"
    if timespent > timeestimate:
        icon = ":bad_condition:"
    elif timespent == timeestimate:
        icon = ":greate_condition:"
    return icon

def create_user_work_times(issues):
    user_work_time = {}
    for issue in issues:
        # print(issue.__dict__)
        worklogs = issue.fields.worklog.worklogs
        issue.fields.timeoriginalestimate = issue.fields.timeoriginalestimate if issue.fields.timeoriginalestimate != None else 0

        for worklog in worklogs:
            # print(worklog.__dict__)
            worker = worklog.author.displayName

            if worker not in user_work_time:
                user_work_time.update({
                    worker: {
                        issue.key: {
                            # チケットあたりの作業時間
                            "spend_time": worklog.timeSpentSeconds/3600,
                            # チケットのサマリー
                            "summary": issue.fields.summary,
                            # 見積時間
                            "timeestimate": issue.fields.timeoriginalestimate/3600,
                            # 消費時間
                            "timespent": issue.fields.timespent/3600,
                            # 状態
                            "condition": get_condition_icon(issue.fields.timespent, issue.fields.timeoriginalestimate)
                        },
                        # 合計作業時間
                        "total": worklog.timeSpentSeconds/3600,
                        # ユーザ画像URL
                        "avatar": worklog.author.avatarUrls.__dict__["48x48"]
                    }
                })
            else:
                worker_spend_times = user_work_time[worker]
                total_spend_time = worker_spend_times["total"]
                if issue.key not in worker_spend_times:
                    worker_spend_times.update({
                        issue.key: {
                            "spend_time": worklog.timeSpentSeconds/3600,
                            "summary": issue.fields.summary,
                            "timeestimate": issue.fields.timeoriginalestimate/3600,
                            "timespent": issue.fields.timespent/3600,
                            "condition": get_condition_icon(issue.fields.timespent, issue.fields.timeoriginalestimate)
                        },
                        "total": total_spend_time + worklog.timeSpentSeconds/3600,
                        "avatar": worklog.author.avatarUrls.__dict__["48x48"]
                    })
                else:
                    # 作業時間を加算
                    spend_time = worker_spend_times[issue.key]["spend_time"] + worklog.timeSpentSeconds/3600
                    worker_spend_times[issue.key].update({
                            "spend_time": spend_time
                        })
                    worker_spend_times.update({
                        "total": total_spend_time + worklog.timeSpentSeconds/3600
                    })
    return user_work_time

def main():

    today = datetime.now().strftime(JIRA_DATE_FORMAT)
    start_of_today = datetime.strptime(today, JIRA_DATE_FORMAT) - timedelta(JIRA_DAY)
    end_of_today = start_of_today + timedelta(days=JIRA_DAY)

    issues =get_jira_issue_worklogs(start_of_today, end_of_today)
    user_work_time = create_user_work_times(issues)
    if len(user_work_time) > 0:
        slack_msg_blocks = []

        for user_name, tasks in user_work_time.items():
            slack_msg_blocks.append(SlackBlockMsg(user_name, tasks).__dict__)

        slack_send_msg(SLACK_CHANNEL_NAME, slack_msg_blocks)
    else:
        block = {
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": "実績入力なし :normal_condition:",
                "emoji": True
            }
        }
        slack_send_msg(SLACK_CHANNEL_NAME, [block])


if __name__ == '__main__':
    main()
