RM=rm -f

NAME=wait-for-vdr-snd-release
SRCS=$(NAME).cpp
LDFLAGS=-Wall -Wextra

.PHONY: install clean

all: $(NAME)

$(NAME): $(OBJS)
	$(CXX) $(LDFLAGS) -o $(NAME) $(SRCS)

install: $(NAME)
	install -m 4755 -D -t $(DESTDIR)/usr/bin/ $(NAME)

clean:
	$(RM) $(OBJS)

distclean: clean
	$(RM) $(NAME)
