/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01927(unsigned int count)
{
    const unsigned int limit = 148u;
    return count > limit ? limit : count;
}
