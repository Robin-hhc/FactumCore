/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05119(unsigned int count)
{
    const unsigned int limit = 130u;
    return count > limit ? limit : count;
}
