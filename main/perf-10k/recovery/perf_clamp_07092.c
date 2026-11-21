/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07092(unsigned int count)
{
    const unsigned int limit = 56u;
    return count > limit ? limit : count;
}
