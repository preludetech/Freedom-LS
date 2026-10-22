/* Sample data for user-communication mockups. */
const UC_PEOPLE = {
  amara:{name:"Amara Okafor",role:"Learner"}, ada:{name:"Ada Lovelace",role:"Instructor"}, grace:{name:"Grace Hopper",role:"TA"},
  kat:{name:"Katherine Johnson",role:"Learner"}, alan:{name:"Alan Turing",role:"TA"}, marcus:{name:"Marcus Webb",role:"Learner"},
  tomas:{name:"Tomás Rivera",role:"Learner"}, priya:{name:"Priya Nair",role:"Learner"}, chen:{name:"Chen Wei",role:"Learner"},
  lebo:{name:"Lebo Dlamini",role:"Learner"}, fatima:{name:"Fatima Zahra",role:"Learner"}, jordan:{name:"Jordan Blake",role:"Learner"},
  sam:{name:"Sam Rivera",role:"Site admin"}
};
const UC_CAT = {
  message:{icon:"chat-circle-text",label:"Message"}, registration:{icon:"user-plus",label:"Course registration"},
  completion:{icon:"seal-check",label:"Course completion"}, application:{icon:"file-text",label:"Application"},
  deadline:{icon:"calendar-blank",label:"Deadline"}
};
const UC_NOTIFS = [
  {id:1,cat:"message",text:"Ada Lovelace sent you 2 new messages",time:"4 min ago",day:"Today",unread:true,about:"Conversation with Ada Lovelace"},
  {id:2,cat:"registration",text:"You're registered for Introduction to Python",time:"2 hours ago",day:"Today",unread:true,about:"Introduction to Python"},
  {id:3,cat:"completion",text:"You completed Data Basics",time:"Yesterday, 16:20",day:"Yesterday",unread:true,about:"Data Basics"},
  {id:4,cat:"application",text:"Your application for Applied Statistics for Public Health Research (January 2027 intake) was approved. You can now register for the first module.",time:"Yesterday, 09:05",day:"Yesterday",unread:false,about:"Applied Statistics for Public Health Research"},
  {id:5,cat:"message",text:"Grace Hopper sent you a message",time:"Mon 21 Sep",day:"Monday 21 September",unread:false,about:"Conversation with Grace Hopper"},
  {id:6,cat:"deadline",text:"Assignment 2 for Introduction to Python is due on Friday 2 October",time:"Mon 21 Sep",day:"Monday 21 September",unread:false,about:"Introduction to Python"},
  {id:7,cat:"registration",text:"You're registered for Data Basics",time:"14 Sep",day:"Monday 14 September",unread:false,about:"Data Basics"},
  {id:8,cat:"completion",text:"You completed Spreadsheet Skills",time:"2 Sep",day:"Wednesday 2 September",unread:false,about:"Spreadsheet Skills"},
];
const UC_NOTIFS_LONG = [...UC_NOTIFS,
  {id:9,cat:"message",text:"Alan Turing sent you a message",time:"1 Sep",day:"Tuesday 1 September",about:"Conversation with Alan Turing"},
  {id:10,cat:"registration",text:"You're registered for Spreadsheet Skills",time:"1 Sep",day:"Tuesday 1 September",about:"Spreadsheet Skills"},
  {id:11,cat:"message",text:"Katherine Johnson sent you 3 new messages",time:"28 Aug",day:"Friday 28 August",about:"Conversation with Katherine Johnson"},
  {id:12,cat:"application",text:"Your application for Introduction to Python was received. We'll tell you here when it has been reviewed.",time:"20 Aug",day:"Thursday 20 August",about:"Introduction to Python"},
  {id:13,cat:"completion",text:"You completed Getting Started with First Class",time:"12 Aug",day:"Wednesday 12 August",about:"Getting Started with First Class"},
  {id:14,cat:"registration",text:"You're registered for Getting Started with First Class",time:"10 Aug",day:"Monday 10 August",about:"Getting Started with First Class"},
];

const UC_LCONVS = [
  {id:"ada",p:"ada",course:"Introduction to Python",last:"One thing to try next: rewrite it with a list comprehension.",time:"10:40",unread:2},
  {id:"grace",p:"grace",course:"Data Basics",last:"Yes, a left join keeps every row from the first table, even where there's no match.",time:"Yesterday",unread:1},
  {id:"kat",p:"kat",course:"Introduction to Python",last:"You: Are you doing the week 3 quiz tonight?",time:"Mon"},
  {id:"alan",p:"alan",course:"Introduction to Python",last:"Thanks, that's sorted now.",time:"12 Sep"},
];
const UC_BLOCKED_CONV = {id:"marcus",p:"marcus",course:"Introduction to Python",last:"You blocked Marcus Webb",time:"8 Sep",blocked:true};

const UC_ADA_THREAD = [
  {sep:"Friday 18 September"},
  {from:"amara",time:"16:05",texts:["Hi Ada, I'm stuck on exercise 4 in the loops module. My loop never stops. Can you take a look?"]},
  {from:"ada",time:"17:20",texts:["Hi Amara. Check where you change the counter. If it's outside the loop, the condition never becomes false.","Paste the loop here if you're still stuck."]},
  {sep:"Today"},
  {from:"amara",time:"09:12",texts:["That was it, thank you! It runs now."]},
  {from:"ada",time:"10:40",texts:["Nice work on the loops exercise.","One thing to try next: rewrite it with a list comprehension. It's in section 4.3."]},
];
const UC_ADA_LONG = [
  {sep:"Monday 7 September"},
  {from:"amara",time:"08:30",texts:["Hi Ada, is the week 1 recording up yet?"]},
  {from:"ada",time:"09:02",texts:["Yes, it's under Module 1 → Recordings."]},
  {sep:"Thursday 10 September"},
  {from:"amara",time:"19:44",texts:["Quick one: do we submit exercises in the player or by email?"]},
  {from:"ada",time:"20:15",texts:["In the player. Each exercise has a Submit button at the bottom. Email isn't checked for submissions."]},
  {from:"amara",time:"20:16",texts:["Got it, thanks."]},
  ...UC_ADA_THREAD
];
const UC_KAT_THREAD = [
  {sep:"Monday 21 September"},
  {from:"kat",time:"18:02",texts:["Hey! Want to go through the week 3 notes together?"]},
  {from:"kat",time:"18:03",hidden:true},
  {from:"amara",time:"18:30",texts:["Sure, but let's keep it to the notes.","Are you doing the week 3 quiz tonight?"]},
];
const UC_MARCUS_THREAD = [
  {sep:"Tuesday 8 September"},
  {from:"marcus",time:"21:10",texts:["Hey, you're in the Python cohort right?"]},
  {from:"amara",time:"21:12",texts:["Yes, why?"]},
  {from:"marcus",time:"21:14",texts:["Send me your quiz answers."]},
  {from:"amara",time:"21:15",texts:["No, we're meant to do the quiz on our own."]},
  {from:"marcus",time:"21:18",texts:["Come on. Just send them or I'll tell the instructor you copied mine."],rep:true},
];

const UC_ECONVS = [
  {id:"tomas",p:"tomas",course:"Python · Sep 2026",last:"Could I get an extension on assignment 2? I've been ill this week.",time:"11:02",unread:1},
  {id:"amara",p:"amara",course:"Python · Sep 2026",last:"You: One thing to try next: rewrite it with a list comprehension.",time:"10:40"},
  {id:"priya",p:"priya",course:"Data Basics · Self-paced",last:"Thanks for the feedback on my project!",time:"Yesterday",unread:1},
  {id:"lebo",p:"lebo",course:"Python · Sep 2026",last:"Is the recording from week 2 available?",time:"Mon",unread:1},
  {id:"chen",p:"chen",course:"Python · Sep 2026",last:"You: See you in Thursday's session.",time:"18 Sep"},
  {id:"fatima",p:"fatima",course:"Python · Jan 2026",last:"You: Well done on finishing the course.",time:"2 Sep"},
];

const UC_PICKER = [
  {label:"Introduction to Python · September 2026 cohort",people:["ada","alan","kat"]},
  {label:"Data Basics",people:["grace"]},
];

Object.assign(window,{UC_PEOPLE,UC_CAT,UC_NOTIFS,UC_NOTIFS_LONG,UC_LCONVS,UC_BLOCKED_CONV,UC_ADA_THREAD,UC_ADA_LONG,UC_KAT_THREAD,UC_MARCUS_THREAD,UC_ECONVS,UC_PICKER});
