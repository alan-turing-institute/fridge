#!/bin/bash

# handle ctrl+c
trap 'echo -e "\nExiting..."; exit 0' INT

COLOR_RED="$(tput setaf 1)"
COLOR_GREEN="$(tput setaf 2)"
COLOR_YELLOW="$(tput setaf 3)"
COLOR_BLUE="$(tput setaf 4)"
COLOR_REST="$(tput sgr0)"


# check if Pulumi is logged in
echo -e "\nChecking Pulumi login status..."
# check if user has PULUMI_ACCESS_TOKEN set
if [ -z "$PULUMI_ACCESS_TOKEN" ]; then
    echo -e "${COLOR_YELLOW}PULUMI_ACCESS_TOKEN is not set. Please set it to log in.${COLOR_REST}"
    echo -e "Run '${COLOR_BLUE}export PULUMI_ACCESS_TOKEN=<your-token>${COLOR_REST}' to set it."
    echo -e "using fake token for now"
    export PULUMI_ACCESS_TOKEN="fake-token"
fi
if ! pulumi whoami > /dev/null 2>&1 && [ $? -eq 0 ]; then
    echo -e "${COLOR_YELLOW}You are not logged in to Pulumi. Please log in first.${COLOR_REST}"
    echo -e "Run '${COLOR_BLUE}pulumi login${COLOR_REST}' to log in."
    if gum confirm "Would you like to use local login?"; then
        pulumi login file:///workspace/infra/fridge/.stack
    else
        echo -e "Please log in to Pulumi using '${COLOR_BLUE}pulumi login <backend-url>${COLOR_REST}'."
        exit 1
    fi
else
    echo -e "You are logged in to Pulumi as ${COLOR_BLUE}$(pulumi whoami)${COLOR_REST}."
fi

# check if the stack exists
echo -e "\n Checking if the Pulumi stack exists..."
pulumi stack ls
if [ $? -ne 0 ]; then
    echo -e "${COLOR_RED}Error listing Pulumi stacks. Please check your Pulumi installation.${COLOR_REST}"
    exit 1
fi
if [ "$(pulumi stack ls --json | jq '. | length == 0')" = "true" ]; then
    echo -e "${COLOR_YELLOW}No stacks found. Please create a stack first.${COLOR_REST}"
    echo -e "Run '${COLOR_BLUE}pulumi stack init <stack-name>${COLOR_REST}' to create a new stack."
    gum confirm "Would you like to create a new stack?" &&
        pulumi stack init dev &&
        pulumi stack select dev
    echo "New stack created and selected."
else
    echo -e "${COLOR_GREEN}Pulumi stack exists.${COLOR_REST}"
fi

echo -e "\nChecking selected stack..."
echo "do we have a current stack?"
if [ ! $(pulumi stack ls --json | jq -e '.[] | .current == true') ]; then
    echo -e "${COLOR_YELLOW}No current stack selected. Please select a stack.${COLOR_REST}"
    echo -e "do we have only one stack?"
    if [ $(pulumi stack ls --json | jq -e '. | length == 1') ]; then
        echo "Only one stack found, setting it as current..."
        pulumi stack select $(pulumi stack ls --json | jq -r '.[0].name')
    else
        echo "Multiple stacks found, please select one to set as current."
        echo -e "Run '${COLOR_BLUE}pulumi stack select <stack-name>${COLOR_REST}' to set a stack as current."
        gum confirm "Would you like to set a stack as current?" && \
        pulumi stack select $(\
        pulumi stack ls --json |
        jq -r '.[] | select(.current == false) | .name' |
        gum filter --placeholder="please select a stack"
        )
    fi

    echo "currently selected stack. $(pulumi stack ls --json | jq -r '.[] | select(.current == true) | .name')"
    pulumi stack ls --json | jq '.[] | select(.current == true) | .name'

echo "do we have multiple stacks?"
elif pulumi stack ls --json | jq -e '. | length >= 2'; then
    gum confirm "Would you like to set a different stack as current?" && \
    pulumi stack unselect && \
    pulumi stack select $(pulumi stack ls --json |
    jq -r '.[] | select(.current == false) | .name' |
    gum filter --placeholder="please select a stack")
fi
