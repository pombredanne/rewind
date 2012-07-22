"""Classes used to simplify communication between different components."""
import zmq

import rewind.messages.eventhandling_pb2 as eventhandling_pb2


class EventQuerier(object):
    """Client that queries events from rewind over ZeroMQ."""
    class QueryException(Exception):
        """Raised when rewind server returns an error.

        Usually this exception means you have used a non-existing query key.
        """
        pass

    def __init__(self, socket):
        """Constructor."""
        self.socket = socket

    def query(self, from_=None, to=None):
        """Make a query of events."""
        stream_request = eventhandling_pb2.EventStreamRangeRequest()
        first_msg = True
        done = False
        while not done:
            # _real_query(...) are giving us events in small batches
            done, events = self._real_query(stream_request, from_, to)
            for event in events:
                if first_msg:
                    assert event.eventid != from_, "First message ID wrong"
                    first_msg = False
                from_ = event.eventid
                yield event

    def _real_query(self, stream_request, from_=None, to=None):
        """Make the actual query for events.

        Since the logbook streams events in batches, this method might not
        receive all requested events.
        """
        if from_:
            stream_request.fro = from_
        if to:
            stream_request.to = to
        etype = eventhandling_pb2.EventRequest.RANGE_STREAM_REQUEST
        request = eventhandling_pb2.EventRequest(type=etype,
                                                 event_range=stream_request)
        self.socket.send(request.SerializeToString())

        more = True
        done = False
        events = []
        stored_event = eventhandling_pb2.StoredEvent()
        while more:
            data = self.socket.recv()
            if data == "END":
                done = True
            elif data == "ERROR":
                raise self.QueryException("Could not query. Event key(s)"
                                          " non-existent?")
            else:
                stored_event.ParseFromString(data)
    
                to_store = eventhandling_pb2.StoredEvent()
                to_store.CopyFrom(stored_event)
                events.append(to_store)

            if not self.socket.getsockopt(zmq.RCVMORE):
                more = False

        return done, events

