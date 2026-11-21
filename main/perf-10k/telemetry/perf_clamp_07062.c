/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07062(unsigned int count)
{
    const unsigned int limit = 44u;
    return count > limit ? limit : count;
}
