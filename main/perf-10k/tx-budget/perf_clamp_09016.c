/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09016(unsigned int count)
{
    const unsigned int limit = 145u;
    return count > limit ? limit : count;
}
