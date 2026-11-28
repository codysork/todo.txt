#!/usr/bin/env bash
#
# @file hooks (todo.sh add-on hook runner)
# @author Cody Sork <codysork@gmail.com> with help from AI agents
# @created 2026-11-22
# @modified 2026-11-27
# @description Run configured hooks for todo.sh add-ons.

todo_run_hooks() {
	local action=$1
	local event=$2
	shift 2

	local hook_dir="${TODO_HOOKS_DIR:-$HOME/.todo/hooks}/$action/${event}.d"
	local hook
	local status
	local LC_ALL=C

	TODO_HOOKS_RUN_COUNT=0
	[[ -d "$hook_dir" ]] || return 0

	for hook in "$hook_dir"/*; do
		[[ -f "$hook" && -x "$hook" ]] || continue
		TODO_HOOKS_RUN_COUNT=$((TODO_HOOKS_RUN_COUNT + 1))

		if TODO_HOOK_ACTION="$action" TODO_HOOK_EVENT="$event" "$hook" "$@"; then
			continue
		else
			status=$?
			echo "Hook failed: $action/$event $(basename "$hook") (exit $status)." >&2
			return "$status"
		fi
	done
}

todo_count_hooks() {
	local action=$1
	local event=$2
	local hook_dir="${TODO_HOOKS_DIR:-$HOME/.todo/hooks}/$action/${event}.d"
	local hook
	local count=0
	local LC_ALL=C

	if [[ -d "$hook_dir" ]]; then
		for hook in "$hook_dir"/*; do
			[[ -f "$hook" && -x "$hook" ]] || continue
			count=$((count + 1))
		done
	fi

	printf '%s' "$count"
}

todo_hooks_usage() {
	echo "Usage: hooks.sh <count|run> ACTION EVENT [ARG...]"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
	command=${1:-}
	shift || true

	case "$command" in
		count)
			[[ $# -eq 2 ]] || {
				todo_hooks_usage >&2
				exit 2
			}
			todo_count_hooks "$1" "$2"
			;;
		run)
			[[ $# -ge 2 ]] || {
				todo_hooks_usage >&2
				exit 2
			}
			action=$1
			event=$2
			shift 2
			todo_run_hooks "$action" "$event" "$@"
			;;
		usage|help|-h|--help)
			todo_hooks_usage
			;;
		*)
			todo_hooks_usage >&2
			exit 2
			;;
	esac
fi
