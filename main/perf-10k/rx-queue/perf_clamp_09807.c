/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09807(unsigned int count)
{
    const unsigned int limit = 146u;
    return count > limit ? limit : count;
}
