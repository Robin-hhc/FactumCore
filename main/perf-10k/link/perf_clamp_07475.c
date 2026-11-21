/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07475(unsigned int count)
{
    const unsigned int limit = 93u;
    return count > limit ? limit : count;
}
